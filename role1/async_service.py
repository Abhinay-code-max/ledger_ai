"""Async Role 1 processing seam for binding to Role 4 request/event adapters.

The request and event types here are Role 1 internal interfaces. A Role 4
integration must map its approved wire contract to these types; this module
does not define or change the shared Role 4 contract.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from .pipeline import (
    MAX_PAGES,
    DocumentReference,
    DocumentStore,
    InvoiceModel,
    process_invoice,
    _validate_schema,
    _failure,
)
from .validator import ContractError, validate_extraction

LOG = logging.getLogger(__name__)
EXPECTED_CONTRACT_VERSION = "role1.document-extraction.v1"
MAX_IN_FLIGHT = 128
MAX_CONCURRENT = 4
MAX_ATTEMPTS = 3
PROCESSING_TIMEOUT_SECONDS = 120.0
MAX_CACHE_ENTRIES = 4096
IDENTIFIER_LIMIT = 256


@dataclass(frozen=True)
class ProcessingRequest:
    """Normalized context supplied by the Role 4 request adapter."""

    tenant_id: str
    document_id: str
    request_id: str
    correlation_id: str
    extraction_id: str
    expected_contract_version: str
    content_sha256: str
    media_type: str
    page_count: int

    def reference(self) -> DocumentReference:
        return DocumentReference(self.document_id, self.tenant_id, self.content_sha256,
                                 self.media_type, self.page_count)


class EventPublisher(Protocol):
    """Role 4 adapter must map this call to its approved event interface.

    The idempotency key is required because event delivery can be retried by
    the transport. The receiver should deduplicate on it.
    """

    async def publish_result(self, *, idempotency_key: str, result: dict[str, Any],
                             operational_metadata: dict[str, Any]) -> None: ...


Processor = Callable[[ProcessingRequest], dict[str, Any]]


def _tag(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _idempotency_key(tenant_id: str, request_id: str, result: dict[str, Any]) -> str:
    # Same-result transport retries deduplicate; a later retry that produces a
    # different outcome (for example, transient failure then success) remains
    # deliverable. Raw identifiers and extracted values never enter the key.
    tenant_digest = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
    request_digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
    result_digest = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":"),
                                               ensure_ascii=False).encode("utf-8")).hexdigest()
    return f"role1:{tenant_digest}:{request_digest}:{result_digest}"


def _fingerprint(request: ProcessingRequest) -> str:
    material = {
        "tenant_id": request.tenant_id,
        "document_id": request.document_id,
        "request_id": request.request_id,
        "correlation_id": request.correlation_id,
        "extraction_id": request.extraction_id,
        "expected_contract_version": request.expected_contract_version,
        "content_sha256": request.content_sha256,
        "media_type": request.media_type,
        "page_count": request.page_count,
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()


class AsyncRole1Service:
    """Bounded async facade with same-process request coalescing.

    This is intentionally not a durable queue or idempotency database. The
    Role 4 adapter remains responsible for durable request/event semantics.
    """

    def __init__(self, *, store: DocumentStore, model: InvoiceModel,
                 publisher: EventPublisher, processor: Processor | None = None,
                 max_concurrent: int = MAX_CONCURRENT,
                 max_attempts: int = MAX_ATTEMPTS,
                 timeout_seconds: float = PROCESSING_TIMEOUT_SECONDS):
        if not 1 <= max_concurrent <= MAX_IN_FLIGHT:
            raise ValueError("max_concurrent is outside the supported bound")
        if not 1 <= max_attempts <= 5:
            raise ValueError("max_attempts is outside the supported bound")
        if not 0 < timeout_seconds <= 600:
            raise ValueError("timeout_seconds is outside the supported bound")
        self._store, self._model, self._publisher = store, model, publisher
        self._processor = processor or self._default_processor
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_attempts = max_attempts
        self._timeout = timeout_seconds
        self._lock = asyncio.Lock()
        self._jobs: dict[tuple[str, str], tuple[str, asyncio.Task[dict[str, Any]]]] = {}

    def _default_processor(self, request: ProcessingRequest) -> dict[str, Any]:
        return process_invoice(reference=request.reference(), store=self._store,
                               model=self._model, correlation_id=request.correlation_id,
                               extraction_id=request.extraction_id)

    @staticmethod
    def _validate_request(request: ProcessingRequest) -> str | None:
        for name in ("tenant_id", "document_id", "request_id", "correlation_id", "extraction_id"):
            value = getattr(request, name, None)
            if not isinstance(value, str) or not value.strip() or len(value) > IDENTIFIER_LIMIT:
                return "INVALID_REQUEST"
        if request.expected_contract_version != EXPECTED_CONTRACT_VERSION:
            return "CONTRACT_VERSION_MISMATCH"
        if (not isinstance(request.content_sha256, str)
                or re.fullmatch(r"[a-f0-9]{64}", request.content_sha256) is None):
            return "INVALID_REQUEST"
        if (not isinstance(request.media_type, str) or not request.media_type.strip() or len(request.media_type) > 128
                or type(request.page_count) is not int or not 1 <= request.page_count <= MAX_PAGES):
            return "REQUEST_LIMIT_EXCEEDED"
        return None

    async def submit(self, request: ProcessingRequest) -> dict[str, Any]:
        """Process a request once per tenant/request key and publish its result."""
        error = self._validate_request(request)
        if error:
            return self._early_failure(request, error)
        key = (request.tenant_id, request.request_id)
        fingerprint = _fingerprint(request)
        async with self._lock:
            existing = self._jobs.get(key)
            if existing:
                if existing[0] != fingerprint:
                    return self._early_failure(request, "IDEMPOTENCY_KEY_REUSED")
                task = existing[1]
                if task.done():
                    try:
                        previous = task.result()
                    except Exception:
                        previous = self._early_failure(request, "PROCESSING_ERROR", retriable=True)
                    if previous.get("failure", {}).get("retriable") is True:
                        task = asyncio.create_task(self._run(request))
                        self._jobs[key] = (fingerprint, task)
            else:
                if len(self._jobs) >= MAX_CACHE_ENTRIES:
                    # Evict completed entries only; never discard an in-flight job.
                    completed = next((k for k, (_, t) in self._jobs.items() if t.done()), None)
                    if completed is None:
                        return self._early_failure(request, "CAPACITY_EXCEEDED", retriable=True)
                    del self._jobs[completed]
                if sum(not task.done() for _, task in self._jobs.values()) >= MAX_IN_FLIGHT:
                    return self._early_failure(request, "CAPACITY_EXCEEDED", retriable=True)
                task = asyncio.create_task(self._run(request))
                self._jobs[key] = (fingerprint, task)
        # Shield shared work from cancellation of any one caller.
        return await asyncio.shield(task)

    async def _run(self, request: ProcessingRequest) -> dict[str, Any]:
        started = time.monotonic()
        attempts = 0
        tenant_tag = _tag(request.tenant_id)
        try:
            async with self._semaphore:
                # A unique temporary workspace per tenant and request prevents
                # accidental cross-tenant path reuse. Current extraction stays
                # memory based, so no source document is copied there.
                with tempfile.TemporaryDirectory(prefix=f"ledgerai-{tenant_tag}-") as temp_dir:
                    if os.name != "nt":
                        Path(temp_dir).chmod(0o700)
                    while attempts < self._max_attempts:
                        attempts += 1
                        try:
                            result = await asyncio.wait_for(
                                asyncio.to_thread(self._processor, request), timeout=self._timeout)
                        except asyncio.TimeoutError:
                            # A Python worker thread cannot be forcibly cancelled.
                            # Classify as terminal so this key cannot launch an
                            # overlapping extraction while the worker may run on.
                            result = self._early_failure(request, "PROCESSING_TIMEOUT")
                        except Exception:
                            # Exception text may contain document data or secrets.
                            LOG.error("Role 1 processing raised an exception tenant_tag=%s request_tag=%s",
                                      tenant_tag, _tag(request.request_id))
                            result = self._early_failure(request, "PROCESSING_ERROR", retriable=True)
                        try:
                            validate_extraction(result)
                            _validate_schema(result)
                            if (result["contract_version"] != request.expected_contract_version
                                    or result["document"]["tenant_id"] != request.tenant_id
                                    or result["document"]["document_id"] != request.document_id
                                    or result["document"]["content_sha256"] != request.content_sha256
                                    or result["document"]["media_type"] != request.media_type
                                    or result["document"]["page_count"] != request.page_count
                                    or result["correlation_id"] != request.correlation_id
                                    or result["extraction_id"] != request.extraction_id):
                                raise ContractError("processor result context mismatch")
                        except (ContractError, KeyError, TypeError):
                            result = self._early_failure(request, "INVALID_PROCESSOR_OUTPUT")
                        retryable = (result.get("status") == "failure"
                                     and result.get("failure", {}).get("retriable") is True)
                        if not retryable or attempts >= self._max_attempts:
                            break
                        await asyncio.sleep(min(0.1 * (2 ** (attempts - 1)), 1.0))
        except Exception:
            # Workspace, semaphore, or cleanup failures are explicit and do not
            # leak exception text into the returned result or logs.
            LOG.error("Role 1 temporary processing setup failed tenant_tag=%s request_tag=%s",
                      tenant_tag, _tag(request.request_id))
            attempts = max(attempts, 1)
            result = self._early_failure(request, "PROCESSING_ERROR", retriable=True)
        metadata = {
            "tenant_tag": _tag(request.tenant_id),
            "request_tag": _tag(request.request_id),
            "correlation_tag": _tag(request.correlation_id),
            "attempts": attempts,
            "duration_ms": min(int((time.monotonic() - started) * 1000), 2**31 - 1),
            "status": result.get("status", "failure"),
            "failure_code": result.get("failure", {}).get("code"),
        }
        try:
            await asyncio.wait_for(self._publisher.publish_result(
                idempotency_key=_idempotency_key(request.tenant_id, request.request_id, result),
                result=result, operational_metadata=metadata), timeout=self._timeout)
        except Exception:
            # Do not log exception text; publisher implementations must dedupe
            # on idempotency_key to make transport retries safe.
            LOG.error("Role 1 result event publish failed tenant_tag=%s request_tag=%s",
                      metadata["tenant_tag"], metadata["request_tag"])
            return self._early_failure(request, "EVENT_PUBLISH_FAILED", retriable=True)
        return result

    @staticmethod
    def _early_failure(request: ProcessingRequest, code: str, *, retriable: bool = False) -> dict[str, Any]:
        # Construct the same versioned failure envelope without echoing
        # untrusted request identifiers when they are malformed.
        safe_ref = DocumentReference(
            document_id=request.document_id if isinstance(getattr(request, "document_id", None), str) and request.document_id.strip() else "invalid",
            tenant_id=request.tenant_id if isinstance(getattr(request, "tenant_id", None), str) and request.tenant_id.strip() else "invalid",
            content_sha256=request.content_sha256 if isinstance(getattr(request, "content_sha256", None), str)
            and re.fullmatch(r"[a-f0-9]{64}", request.content_sha256) else "0" * 64,
            media_type=request.media_type if isinstance(getattr(request, "media_type", None), str) and request.media_type.strip() else "application/octet-stream",
            page_count=request.page_count if type(getattr(request, "page_count", None)) is int and request.page_count > 0 else 1,
        )
        return _failure(safe_ref,
                        request.correlation_id if isinstance(getattr(request, "correlation_id", None), str) and request.correlation_id.strip() else "invalid",
                        code, "Request could not be processed", retriable,
                        extraction_id=request.extraction_id if isinstance(getattr(request, "extraction_id", None), str) and request.extraction_id.strip() else "invalid")
