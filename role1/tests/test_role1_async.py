"""Phase 3 Role 1 async boundary checks using local fake adapters."""
import asyncio
import json
import threading
import time
import unittest
from copy import deepcopy
from pathlib import Path

from role1.async_service import AsyncRole1Service, ProcessingRequest
from role1.role4_adapter import Role4RequestAdapter
from role1.validator import validate_extraction

ROOT = Path(__file__).resolve().parents[1]
PACK = json.loads((ROOT / "fixtures" / "evaluation-v1.json").read_text(encoding="utf-8-sig"))
CLEAN = next(deepcopy(f["expected"]) for f in PACK["fixtures"] if f["case_id"] == "clean_invoice")
FAILED = next(deepcopy(f["expected"]) for f in PACK["fixtures"] if f["case_id"] == "terminal_failure")


class Store:
    def open_read(self, *, tenant_id, document_id):
        raise AssertionError("custom processor should be used")


class Model:
    model_version = "unused"


class Publisher:
    def __init__(self):
        self.events = []

    async def publish_result(self, *, idempotency_key, result, operational_metadata):
        self.events.append((idempotency_key, deepcopy(result), dict(operational_metadata)))


def request(tenant="tenant-a", request_id="request-1"):
    return ProcessingRequest(
        tenant_id=tenant, document_id="doc-1", request_id=request_id,
        correlation_id="corr-1", extraction_id="ext-1",
        expected_contract_version="role1.document-extraction.v1",
        content_sha256="a" * 64, media_type="application/pdf", page_count=1,
    )


def result_for(req):
    result = deepcopy(CLEAN)
    result["document"].update(document_id=req.document_id, tenant_id=req.tenant_id,
                               content_sha256=req.content_sha256, media_type=req.media_type,
                               page_count=req.page_count)
    result.update(extraction_id=req.extraction_id, correlation_id=req.correlation_id)
    return result


def retriable_failure_for(req):
    result = deepcopy(FAILED)
    result["document"].update(document_id=req.document_id, tenant_id=req.tenant_id,
                               content_sha256=req.content_sha256, media_type=req.media_type,
                               page_count=req.page_count)
    result["failure"].update(code="MODEL_UNAVAILABLE", message="Extraction service unavailable",
                              retriable=True)
    result.update(extraction_id=req.extraction_id, correlation_id=req.correlation_id)
    return result


class AsyncServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_tenant_concurrent_retry_coalesces_and_publishes_once(self):
        calls = []

        def processor(req):
            calls.append(req.tenant_id)
            return result_for(req)

        publisher = Publisher()
        service = AsyncRole1Service(store=Store(), model=Model(), publisher=publisher,
                                    processor=processor, max_concurrent=2)
        req = request()
        one, two = await asyncio.gather(service.submit(req), service.submit(req))
        self.assertEqual(one, two)
        validate_extraction(one)
        self.assertEqual(calls, ["tenant-a"])
        self.assertEqual(len(publisher.events), 1)
        event_key = publisher.events[0][0]
        self.assertNotIn(req.tenant_id, event_key)
        self.assertNotIn(req.request_id, event_key)
        metadata = publisher.events[0][2]
        self.assertNotIn(req.tenant_id, json.dumps(metadata))
        self.assertNotIn(req.request_id, json.dumps(metadata))

    async def test_same_request_id_across_tenants_never_shares_result(self):
        calls = []

        def processor(req):
            calls.append(req.tenant_id)
            return result_for(req)

        publisher = Publisher()
        service = AsyncRole1Service(store=Store(), model=Model(), publisher=publisher,
                                    processor=processor, max_concurrent=2)
        a, b = await asyncio.gather(service.submit(request("tenant-a")),
                                     service.submit(request("tenant-b")))
        self.assertEqual({a["document"]["tenant_id"], b["document"]["tenant_id"]},
                         {"tenant-a", "tenant-b"})
        self.assertCountEqual(calls, ["tenant-a", "tenant-b"])
        self.assertEqual(len(publisher.events), 2)
        validate_extraction(a)
        validate_extraction(b)

    async def test_retriable_result_can_be_retried_with_same_idempotency_key(self):
        attempts = []

        def processor(req):
            attempts.append(1)
            if len(attempts) == 1:
                return retriable_failure_for(req)
            return result_for(req)

        publisher = Publisher()
        service = AsyncRole1Service(store=Store(), model=Model(), publisher=publisher,
                                    processor=processor, max_attempts=1)
        req = request()
        first = await service.submit(req)
        self.assertTrue(first["failure"]["retriable"])
        second = await service.submit(req)
        self.assertEqual(second["status"], "success")
        self.assertEqual(len(attempts), 2)
        self.assertEqual(len(publisher.events), 2)
        # A changed retry outcome gets a new event key, so a consumer that has
        # seen the transient failure can still accept the later success.
        self.assertNotEqual(publisher.events[0][0], publisher.events[1][0])

    async def test_wrong_tenant_processor_result_is_rejected_before_publish(self):
        publisher = Publisher()
        calls = []

        def wrong_tenant(req):
            calls.append(req.request_id)
            result = result_for(req)
            result["document"]["tenant_id"] = "other-tenant"
            return result

        service = AsyncRole1Service(store=Store(), model=Model(), publisher=publisher,
                                    processor=wrong_tenant, max_attempts=1)
        result = await service.submit(request())
        self.assertEqual(result["failure"]["code"], "INVALID_PROCESSOR_OUTPUT")
        self.assertFalse(result["failure"]["retriable"])
        validate_extraction(result)
        self.assertEqual(len(publisher.events), 1)
        self.assertEqual(calls, ["request-1"])

    async def test_document_hash_media_page_and_correlation_mismatches_are_rejected(self):
        mutations = {
            "content_sha256": lambda r: r["document"].update(content_sha256="b" * 64),
            "media_type": lambda r: r["document"].update(media_type="image/png"),
            "page_count": lambda r: r["document"].update(page_count=2),
            "correlation_id": lambda r: r.update(correlation_id="other-correlation"),
            "extraction_id": lambda r: r.update(extraction_id="other-extraction"),
        }
        for name, mutate in mutations.items():
            with self.subTest(context=name):
                publisher = Publisher()

                def mismatched(req, mutate=mutate):
                    result = result_for(req)
                    mutate(result)
                    return result

                service = AsyncRole1Service(store=Store(), model=Model(), publisher=publisher,
                                            processor=mismatched)
                result = await service.submit(request(request_id=f"request-{name}"))
                self.assertEqual(result["failure"]["code"], "INVALID_PROCESSOR_OUTPUT")
                self.assertFalse(result["failure"]["retriable"])
                validate_extraction(result)
                self.assertEqual(publisher.events[0][1], result)

    async def test_schema_invalid_processor_result_is_terminal(self):
        publisher = Publisher()
        calls = []

        def schema_invalid(req):
            calls.append(1)
            result = result_for(req)
            # The semantic Python validator is permissive for this unsupported
            # scalar type; the versioned JSON Schema must reject it.
            result["fields"]["invoice_number"]["value"] = ("tuple", "value")
            return result

        service = AsyncRole1Service(store=Store(), model=Model(), publisher=publisher,
                                    processor=schema_invalid, max_attempts=3)
        result = await service.submit(request())
        self.assertEqual(result["failure"]["code"], "INVALID_PROCESSOR_OUTPUT")
        self.assertFalse(result["failure"]["retriable"])
        self.assertEqual(calls, [1])
        validate_extraction(result)

    async def test_sync_processor_timeout_is_terminal_and_not_retried(self):
        calls = []

        def slow(req):
            calls.append(req.request_id)
            time.sleep(0.04)
            return result_for(req)

        publisher = Publisher()
        service = AsyncRole1Service(store=Store(), model=Model(), publisher=publisher,
                                    processor=slow, max_attempts=3, timeout_seconds=0.005)
        result = await service.submit(request())
        self.assertEqual(result["failure"]["code"], "PROCESSING_TIMEOUT")
        self.assertFalse(result["failure"]["retriable"])
        self.assertEqual(calls, ["request-1"])
        self.assertEqual(len(publisher.events), 1)

    async def test_worker_concurrency_limit_is_enforced_across_tenants(self):
        lock = threading.Lock()
        active = 0
        max_active = 0

        def processor(req):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.025)
            result = result_for(req)
            with lock:
                active -= 1
            return result

        publisher = Publisher()
        service = AsyncRole1Service(store=Store(), model=Model(), publisher=publisher,
                                    processor=processor, max_concurrent=2)
        requests = [request(f"tenant-{i}", f"request-{i}") for i in range(6)]
        results = await asyncio.gather(*(service.submit(req) for req in requests))
        self.assertLessEqual(max_active, 2)
        self.assertEqual({r["document"]["tenant_id"] for r in results},
                         {f"tenant-{i}" for i in range(6)})
        self.assertEqual(len(publisher.events), 6)

    async def test_retriable_attempts_stop_at_configured_bound(self):
        calls = []

        def always_unavailable(req):
            calls.append(req.request_id)
            return retriable_failure_for(req)

        publisher = Publisher()
        service = AsyncRole1Service(store=Store(), model=Model(), publisher=publisher,
                                    processor=always_unavailable, max_attempts=2)
        result = await service.submit(request())
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["failure"]["code"], "MODEL_UNAVAILABLE")
        self.assertTrue(result["failure"]["retriable"])

    async def test_reused_key_with_different_request_is_terminal(self):
        publisher = Publisher()
        service = AsyncRole1Service(store=Store(), model=Model(), publisher=publisher,
                                    processor=result_for)
        await service.submit(request())
        changed = request()
        changed = ProcessingRequest(**{**changed.__dict__, "content_sha256": "b" * 64})
        result = await service.submit(changed)
        self.assertEqual(result["failure"]["code"], "IDEMPOTENCY_KEY_REUSED")
        self.assertFalse(result["failure"]["retriable"])

    async def test_contract_version_and_page_limits_are_explicit(self):
        publisher = Publisher()
        service = AsyncRole1Service(store=Store(), model=Model(), publisher=publisher,
                                    processor=result_for)
        bad_version = request()
        bad_version = ProcessingRequest(**{**bad_version.__dict__,
                                           "expected_contract_version": "future-version"})
        self.assertEqual((await service.submit(bad_version))["failure"]["code"],
                         "CONTRACT_VERSION_MISMATCH")
        too_many_pages = request()
        too_many_pages = ProcessingRequest(**{**too_many_pages.__dict__, "page_count": 21})
        self.assertEqual((await service.submit(too_many_pages))["failure"]["code"],
                         "REQUEST_LIMIT_EXCEEDED")

    async def test_injected_role4_request_mapper_feeds_normalized_context(self):
        class ApprovedMessage:
            pass

        class Mapper:
            def to_role1_request(self, message):
                self.seen = message
                return request(tenant="tenant-from-approved-mapper", request_id="mapped-request")

        mapper = Mapper()
        publisher = Publisher()
        service = AsyncRole1Service(store=Store(), model=Model(), publisher=publisher,
                                    processor=result_for)
        adapter = Role4RequestAdapter(mapper=mapper, service=service)
        message = ApprovedMessage()
        result = await adapter.handle(message)
        self.assertIs(mapper.seen, message)
        self.assertEqual(result["document"]["tenant_id"], "tenant-from-approved-mapper")
        self.assertEqual(result["extraction_id"], "ext-1")
        validate_extraction(result)


if __name__ == "__main__":
    unittest.main()
