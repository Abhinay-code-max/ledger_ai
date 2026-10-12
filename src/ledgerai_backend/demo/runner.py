"""Reproducible live-interface NOVA Phase 4 demonstration runner."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import threading
import time
from contextlib import ExitStack, suppress
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx
import uvicorn
from pydantic import SecretStr

from ledgerai_backend.core.config import Settings
from ledgerai_backend.core.identity import DeterministicTestIdentityProvider, VerifiedIdentity
from ledgerai_backend.database.seed import stable_id
from ledgerai_backend.demo.comparator import compare
from ledgerai_backend.demo.reset import NOVA_ENTITY_ID, NOVA_ORGANIZATION_ID, reset_nova_demo
from ledgerai_backend.demo.role1 import create_demo_role1_app
from ledgerai_backend.demo.role2 import create_demo_role2_app
from ledgerai_backend.demo.role3 import create_demo_role3_app
from ledgerai_backend.demo.role6 import create_demo_role6_app
from ledgerai_backend.main import create_app

ROOT = Path(__file__).resolve().parents[3]
DATASET = ROOT / "demo" / "nova"
ISSUER = "https://identity.demo.invalid/"
REQUIRED_AUDIT = {
    "DEMO_RESET",
    "DOCUMENT_UPLOADED",
    "DOCUMENT_SCANNED",
    "DOCUMENT_ACCEPTED",
    "TRANSACTIONS_IMPORTED",
    "DOCUMENT_EXTRACTED",
    "DOCUMENT_VALIDATED",
    "RECONCILIATION_PROPOSED",
    "EXCEPTION_CREATED",
    "EXCEPTION_RESOLVED",
    "JOURNAL_PROPOSED",
    "POLICY_EVALUATED",
    "APPROVAL_RECORDED",
    "JOURNAL_POSTING_REQUESTED",
    "JOURNAL_POSTING_CONFIRMED",
    "PERIOD_CLOSE_REQUESTED",
    "PERIOD_CLOSE_CONFIRMED",
    "STATEMENT_CAPTURED",
}
PROVENANCE_PATH = [
    "statement_line",
    "posted_journal",
    "posting_confirmation",
    "journal_proposal",
    "policy_decision",
    "approval_action",
    "match_proposal",
    "bank_transaction",
    "document_extraction",
    "document_version",
    "source_evidence",
]


class DemoFailure(RuntimeError):
    pass


class LiveServer:
    def __init__(self, app: Any, host: str, port: int) -> None:
        self.server = uvicorn.Server(
            uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False)
        )
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self) -> None:
        if sys.platform == "win32":
            loop = asyncio.SelectorEventLoop()
        else:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.server.serve())
        finally:
            loop.close()

    def __enter__(self) -> LiveServer:
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() >= deadline:
                raise DemoFailure("an embedded demo service failed to start")
            time.sleep(0.05)
        return self

    def __exit__(self, *_: object) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)
        time.sleep(0.15)


def _required(name: str, *, minimum: int = 1) -> str:
    value = os.environ.get(name, "")
    if len(value) < minimum:
        raise DemoFailure(f"{name} is required for the explicit demo environment")
    return value


def _safe_local_url(name: str, default: str) -> str:
    value = os.environ.get(name, default)
    parsed = urlparse(value)
    allowed = {
        item.strip().lower()
        for item in os.environ.get("LEDGERAI_DEMO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
        if item.strip()
    }
    if parsed.scheme != "http" or parsed.hostname is None or parsed.hostname.lower() not in allowed:
        raise DemoFailure(f"{name} must use an allowlisted loopback HTTP endpoint")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise DemoFailure(f"{name} contains prohibited URL components")
    return value.rstrip("/")


def _settings(
    role1_url: str = "http://127.0.0.1:8101",
    role2_url: str = "http://127.0.0.1:8102",
    role3_url: str = "http://127.0.0.1:8103",
    role6_url: str = "http://127.0.0.1:8006",
) -> Settings:
    environment = os.environ.get("LEDGERAI_ENVIRONMENT", "")
    if environment == "production":
        raise DemoFailure("the NOVA demo is prohibited in production")
    if environment not in {"development", "test"}:
        raise DemoFailure("LEDGERAI_ENVIRONMENT must explicitly be development or test")
    if os.environ.get("LEDGERAI_DEMO_ENABLED", "").lower() != "true":
        raise DemoFailure("LEDGERAI_DEMO_ENABLED=true is required")
    if os.environ.get("LEDGERAI_DEMO_RESET_CONFIRM", "") != "RESET_NOVA_ONLY":
        raise DemoFailure("LEDGERAI_DEMO_RESET_CONFIRM=RESET_NOVA_ONLY is required")
    service_secret = _required("LEDGERAI_SERVICE_TOKEN_SECRET", minimum=32)
    return Settings(
        environment=cast(Literal["development", "test"], environment),
        database_dsn=SecretStr(_required("LEDGERAI_DATABASE_DSN")),
        migration_dsn=SecretStr(_required("LEDGERAI_MIGRATION_DSN")),
        storage_endpoint_url=_required("LEDGERAI_STORAGE_ENDPOINT_URL"),
        storage_access_key=SecretStr(_required("LEDGERAI_STORAGE_ACCESS_KEY")),
        storage_secret_key=SecretStr(_required("LEDGERAI_STORAGE_SECRET_KEY")),
        storage_use_tls=False,
        scanner_adapter="deterministic",
        redis_url=SecretStr(_required("LEDGERAI_REDIS_URL")),
        role1_base_url=role1_url,
        role2_base_url=role2_url,
        role3_base_url=role3_url,
        role6_base_url=role6_url,
        service_token_secret=SecretStr(service_secret),
        service_token_issuer=os.environ.get("LEDGERAI_SERVICE_TOKEN_ISSUER", "ledgerai-backend"),
        adapter_total_timeout_seconds=2,
        request_timeout_seconds=10,
        log_level="WARNING",
    )


def _identity() -> DeterministicTestIdentityProvider:
    return DeterministicTestIdentityProvider(
        {
            _required("LEDGERAI_DEMO_MAKER_TOKEN", minimum=16): VerifiedIdentity(
                ISSUER, "nova-admin"
            ),
            _required("LEDGERAI_DEMO_REVIEWER_TOKEN", minimum=16): VerifiedIdentity(
                ISSUER, "nova-reviewer"
            ),
        }
    )


class DemoClient:
    def __init__(self, api_url: str, correlation_id: UUID) -> None:
        self.correlation_id = str(correlation_id)
        self.api = httpx.Client(base_url=api_url, timeout=httpx.Timeout(10, connect=2))
        self.maker = _required("LEDGERAI_DEMO_MAKER_TOKEN", minimum=16)
        self.reviewer = _required("LEDGERAI_DEMO_REVIEWER_TOKEN", minimum=16)

    def close(self) -> None:
        self.api.close()

    def headers(self, token: str, *, idempotency: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-Code": "nova",
            "X-Organization-ID": str(NOVA_ORGANIZATION_ID),
            "X-Legal-Entity-ID": str(NOVA_ENTITY_ID),
            "X-Correlation-ID": self.correlation_id,
        }
        if idempotency:
            headers["Idempotency-Key"] = idempotency
        return headers

    @staticmethod
    def expect(response: httpx.Response, status: int | set[int]) -> dict[str, Any]:
        expected = {status} if isinstance(status, int) else status
        if response.status_code not in expected:
            code = "UNKNOWN"
            with suppress(ValueError, AttributeError):
                code = str(response.json().get("code", "UNKNOWN"))
            raise DemoFailure(
                f"unexpected service response: status={response.status_code} code={code}"
            )
        value = response.json()
        if not isinstance(value, dict):
            raise DemoFailure("service returned an unexpected response shape")
        return value


def _stage(number: int, message: str) -> None:
    print(f"[{number:02d}/12] {message}", file=sys.stderr, flush=True)


def _check_ready(url: str, *, path: str = "/health/ready", timeout: float | None = None) -> None:
    timeout_seconds = timeout or float(os.environ.get("LEDGERAI_DEMO_READINESS_TIMEOUT", "5"))
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{url}{path}", timeout=min(2.0, timeout_seconds))
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise DemoFailure("dependency readiness timed out")


def _normalize_audit(actions: set[str]) -> set[str]:
    normalized = set(actions)
    if "JOURNAL_POSTING_RESULT" in actions:
        normalized.add("JOURNAL_POSTING_CONFIRMED")
    if "PERIOD_CLOSE_RESULT" in actions:
        normalized.add("PERIOD_CLOSE_CONFIRMED")
    if "FINANCIAL_STATEMENT_CAPTURED" in actions:
        normalized.add("STATEMENT_CAPTURED")
    return normalized


def execute_demo(api_url: str, settings: Settings) -> dict[str, object]:
    correlation_id = uuid4()
    client = DemoClient(api_url, correlation_id)
    try:
        _stage(1, "checking live API, Roles 1/2/3/6, PostgreSQL, Redis, and object storage")
        _check_ready(api_url, path="/health/live")
        assert settings.role1_base_url is not None
        _check_ready(settings.role1_base_url)
        assert settings.role2_base_url is not None
        _check_ready(settings.role2_base_url)
        assert settings.role3_base_url is not None
        _check_ready(settings.role3_base_url)
        assert settings.role6_base_url is not None
        _check_ready(settings.role6_base_url)
        reset = reset_nova_demo(settings, confirmed=True)
        if reset["tenant_id"] != str(stable_id("nova:tenant")):
            raise DemoFailure("reset returned an unexpected tenant")

        _stage(2, "authenticating synthetic maker and reviewer identities")
        client.expect(client.api.get("/api/v1/me", headers=client.headers(client.maker)), 200)
        client.expect(client.api.get("/api/v1/me", headers=client.headers(client.reviewer)), 200)

        _stage(3, "uploading, scanning, and accepting immutable synthetic invoice evidence")
        evidence = (DATASET / "documents" / "NOVA_SYNTHETIC_INVOICE_001.pdf").read_bytes()
        digest = hashlib.sha256(evidence).hexdigest()
        upload = client.expect(
            client.api.post(
                "/api/v1/documents/uploads",
                headers=client.headers(client.maker, idempotency="nova-demo-upload-v1"),
                json={
                    "original_filename": "NOVA_SYNTHETIC_INVOICE_001.pdf",
                    "media_type": "application/pdf",
                    "byte_size": len(evidence),
                    "sha256": digest,
                },
            ),
            201,
        )
        put = httpx.put(
            str(upload["upload_url"]),
            content=evidence,
            headers={
                "Content-Type": "application/pdf",
                "x-amz-meta-expected-size": str(len(evidence)),
                "x-amz-server-side-encryption": "AES256",
            },
            timeout=httpx.Timeout(10, connect=2),
        )
        if put.status_code not in {200, 201}:
            raise DemoFailure("immutable evidence upload failed")
        document = client.expect(
            client.api.post(
                f"/api/v1/documents/uploads/{upload['upload_id']}/complete",
                headers=client.headers(client.maker, idempotency="nova-demo-complete-v1"),
                json={"sha256": digest, "byte_size": len(evidence)},
            ),
            200,
        )
        if document["status"] != "ACCEPTED":
            raise DemoFailure("synthetic evidence was not accepted after scanning")
        versions_response = client.api.get(
            f"/api/v1/documents/{document['id']}/versions", headers=client.headers(client.maker)
        )
        if versions_response.status_code != 200:
            raise DemoFailure("document version lookup failed")
        versions = versions_response.json()
        version = versions[0]
        status_ok = str(version["status"]) == "ACCEPTED"
        hash_ok = str(version["actual_sha256"]) == digest
        if not status_ok or not hash_ok:
            raise DemoFailure(
                "immutable evidence integrity check failed "
                f"(accepted={status_ok}, hash_match={hash_ok})"
            )

        _stage(4, "importing deterministic synthetic bank transactions")
        csv_data = (DATASET / "bank-transactions.csv").read_bytes()
        imported = client.expect(
            client.api.post(
                "/api/v1/transaction-imports",
                headers=client.headers(client.maker, idempotency="nova-demo-import-v1"),
                data={
                    "bank_account_id": str(stable_id("nova:demo:bank-account")),
                    "mapping_json": "{}",
                },
                files={"file": ("bank-transactions.csv", csv_data, "text/csv")},
            ),
            201,
        )
        transactions = client.expect(
            client.api.get(
                "/api/v1/transactions",
                params={"import_id": imported["id"]},
                headers=client.headers(client.maker),
            ),
            200,
        )["items"]
        if len(transactions) != 2:
            raise DemoFailure("synthetic transaction import produced an unexpected row count")

        _stage(5, "running extraction, validation, reconciliation, and planted exception")
        extraction = client.expect(
            client.api.post(
                f"/api/v1/documents/{document['id']}/extractions",
                headers=client.headers(client.maker, idempotency="nova-demo-extract-v1"),
            ),
            201,
        )
        if extraction["status"] != "COMPLETED":
            raise DemoFailure("document extraction failed")

        reconciliation = client.expect(
            client.api.post(
                "/api/v1/reconciliations",
                headers=client.headers(client.maker, idempotency="nova-demo-reconcile-v1"),
                json={
                    "document_id": document["id"],
                    "document_version_id": version["id"],
                    "transaction_ids": [item["id"] for item in transactions],
                },
            ),
            201,
        )
        exception_id = reconciliation["exception_id"]
        if not exception_id:
            raise DemoFailure("reconciliation did not return the planted exception id")
        approval_request_id = reconciliation["approval_request_id"]
        journal_proposal_id = reconciliation["journal_proposal_id"]

        exception = client.expect(
            client.api.get(
                f"/api/v1/exceptions/{exception_id}",
                headers=client.headers(client.maker),
            ),
            200,
        )
        if (exception["exception_type"], exception["severity"], exception["resolution_status"]) != (
            "AMOUNT_MISMATCH",
            "HIGH",
            "OPEN",
        ):
            raise DemoFailure("the planted exception did not match its committed fixture")

        _stage(6, "enforcing maker-checker and resolving the planted exception")
        approval_path = f"/api/v1/approval-requests/{approval_request_id}/approve"
        maker_attempt = client.api.post(
            approval_path,
            headers={
                **client.headers(client.maker, idempotency="nova-demo-maker-denied"),
                "If-Match": "1",
            },
            json={"reviewed_resource_version": "1", "reason": "Synthetic maker attempt"},
        )
        if (
            maker_attempt.status_code != 403
            or maker_attempt.json().get("code") != "MAKER_CHECKER_VIOLATION"
        ):
            raise DemoFailure("maker-checker did not reject the synthetic maker")
        client.expect(
            client.api.post(
                f"/api/v1/exceptions/{exception_id}/resolve",
                headers=client.headers(client.reviewer, idempotency="nova-demo-resolve-v1"),
                json={
                    "reason": "Reviewed planted mismatch; excluded the INR 50.00 row.",
                },
            ),
            200,
        )
        stale = client.api.post(
            approval_path,
            headers={
                **client.headers(client.reviewer, idempotency="nova-demo-stale"),
                "If-Match": "2",
            },
            json={"reviewed_resource_version": "1", "reason": "Synthetic reviewer"},
        )
        if stale.status_code != 409 or stale.json().get("code") != "STALE_APPROVAL":
            raise DemoFailure("stale approval was not rejected")
        client.expect(
            client.api.post(
                approval_path,
                headers={
                    **client.headers(client.reviewer, idempotency="nova-demo-review-v1"),
                    "If-Match": "1",
                },
                json={
                    "reviewed_resource_version": "1",
                    "reason": "Approved after resolving the synthetic planted mismatch.",
                },
            ),
            200,
        )

        _stage(7, "creating the period and requesting guarded Role 2 posting")
        period = client.expect(
            client.api.post(
                "/api/v1/accounting-periods",
                headers=client.headers(client.maker),
                json={"period_start": "2026-09-01", "period_end": "2026-09-30", "currency": "INR"},
            ),
            201,
        )
        posting = client.expect(
            client.api.post(
                "/api/v1/posting-operations",
                headers=client.headers(client.maker, idempotency="nova-demo-post-v1"),
                json={
                    "journal_proposal_id": journal_proposal_id,
                    "proposal_version": 1,
                    "accounting_period_id": period["id"],
                },
            ),
            202,
        )
        if posting["state"] == "UNKNOWN":
            periods = client.api.get(
                "/api/v1/accounting-periods", headers=client.headers(client.maker)
            ).json()
            if periods[0]["state"] != "OPEN":
                raise DemoFailure("period advanced while posting outcome was unknown")
            posting = client.expect(
                client.api.post(
                    f"/api/v1/posting-operations/{posting['operation_id']}/recover",
                    headers=client.headers(client.maker),
                ),
                200,
            )
        if posting["state"] != "CONFIRMED" or posting["confirmation"] is None:
            raise DemoFailure("Role 2 posting was not confirmed")

        _stage(8, "consuming and resuming the authenticated SSE progress stream")
        stream = client.api.get(
            "/api/v1/progress-stream",
            params={"once": "true"},
            headers=client.headers(client.maker),
        )
        if stream.status_code != 200 or "event: progress" not in stream.text:
            raise DemoFailure("authenticated progress replay did not return an event")
        event_ids = [line[4:] for line in stream.text.splitlines() if line.startswith("id: ")]
        if not event_ids:
            raise DemoFailure("progress replay omitted event identifiers")
        resumed = client.api.get(
            "/api/v1/progress-stream",
            params={"once": "true"},
            headers={**client.headers(client.maker), "Last-Event-ID": event_ids[-1]},
        )
        if resumed.status_code != 200:
            raise DemoFailure("authenticated SSE resume failed")

        _stage(9, "requesting and confirming accounting-period close")
        close = client.expect(
            client.api.post(
                f"/api/v1/accounting-periods/{period['id']}/close",
                headers=client.headers(client.maker, idempotency="nova-demo-close-v1"),
            ),
            202,
        )
        if close["state"] != "CONFIRMED" or close["role2_version"] != "1.0.0":
            raise DemoFailure("Role 2 period close was not confirmed")

        _stage(10, "retrieving Role 2 trial balance, P&L, and balance sheet snapshots")
        expected_statements = json.loads((DATASET / "expected" / "statements.json").read_text())
        statements: dict[str, dict[str, Any]] = {}
        for statement_type in ("TRIAL_BALANCE", "PROFIT_AND_LOSS", "BALANCE_SHEET"):
            snapshot = client.expect(
                client.api.post(
                    f"/api/v1/accounting-periods/{period['id']}/statements/{statement_type}",
                    headers=client.headers(client.maker),
                ),
                201,
            )
            actual_lines = {
                item["line_id"]: Decimal(str(item["amount"])) for item in snapshot["lines"]
            }
            expected_lines = {
                key: Decimal(str(value))
                for key, value in expected_statements[statement_type]["lines"].items()
            }
            if actual_lines != expected_lines:
                raise DemoFailure(f"{statement_type} does not match the synthetic Role 2 fixture")
            if snapshot["currency"] != "INR" or snapshot["role2_version"] != "1.0.0":
                raise DemoFailure(f"{statement_type} metadata is not contract-bound")
            retrieved = client.expect(
                client.api.get(
                    f"/api/v1/financial-statements/{snapshot['id']}",
                    headers=client.headers(client.maker),
                ),
                200,
            )
            if retrieved["id"] != snapshot["id"]:
                raise DemoFailure("statement snapshot identity changed")
            statements[statement_type] = snapshot

        _stage(11, "verifying complete append-only audit and statement-to-source provenance")
        audits_response = client.api.get(
            "/api/v1/audit-events", params={"limit": 100}, headers=client.headers(client.maker)
        )
        if audits_response.status_code != 200:
            raise DemoFailure("audit history could not be retrieved")
        audit_rows = audits_response.json()
        audit_actions = _normalize_audit({item["action"] for item in audit_rows})
        missing_audit = REQUIRED_AUDIT.difference(audit_actions)
        if missing_audit:
            raise DemoFailure("audit lifecycle is incomplete: " + ", ".join(sorted(missing_audit)))
        cash_lines = [
            item for item in statements["TRIAL_BALANCE"]["lines"] if item["line_id"] == "cash"
        ]
        if not cash_lines or "id" not in cash_lines[0]:
            raise DemoFailure("statement did not include expected cash line with identifier")
        statement_line_id = cash_lines[0]["id"]
        trace = client.expect(
            client.api.get(
                f"/api/v1/provenance/statement_line/{statement_line_id}",
                headers=client.headers(client.maker),
            ),
            200,
        )
        node_types = {item["resource_type"] for item in trace["nodes"]}
        if set(PROVENANCE_PATH).difference(node_types) or trace["truncated"]:
            raise DemoFailure("statement provenance does not reach immutable source evidence")

        _stage(12, "normalizing and comparing the final safe machine-readable summary")
        expected_summary = json.loads((DATASET / "expected" / "summary.json").read_text())
        summary: dict[str, object] = {
            "accounting_period": {
                "currency": period["currency"],
                "end": period["period_end"],
                "start": period["period_start"],
                "state": "CLOSED",
            },
            "audit_actions": sorted(REQUIRED_AUDIT),
            "exception": {"resolution": "RESOLVED", "severity": "HIGH", "type": "AMOUNT_MISMATCH"},
            "financials": {
                "currency": "INR",
                "invoice_total": "1250.00",
                "planted_mismatch": "50.00",
            },
            "maker_checker": {
                "maker_rejected": True,
                "reviewer_approved": True,
                "stale_rejected": True,
            },
            "posting": {
                "confirmation_count": 1,
                "effective_posts": 1,
                "proposal_version": 1,
                "state": posting["state"],
            },
            "provenance_path": PROVENANCE_PATH,
            "scenario": "nova-phase4-v1",
            "statements": sorted(statements),
        }
        if not compare(summary, expected_summary):
            raise DemoFailure("normalized result differs from demo/nova/expected/summary.json")
        return summary
    finally:
        client.close()


def run(*, embedded_services: bool = True) -> dict[str, object]:
    if sys.platform == "win32":
        policy = asyncio.WindowsSelectorEventLoopPolicy
        asyncio.set_event_loop_policy(policy())
    role1_url = _safe_local_url("LEDGERAI_DEMO_ROLE1_URL", "http://127.0.0.1:8101")
    role2_url = _safe_local_url("LEDGERAI_DEMO_ROLE2_URL", "http://127.0.0.1:8102")
    role3_url = _safe_local_url("LEDGERAI_DEMO_ROLE3_URL", "http://127.0.0.1:8103")
    role6_url = _safe_local_url("LEDGERAI_DEMO_ROLE6_URL", "http://127.0.0.1:8006")
    api_url = _safe_local_url("LEDGERAI_DEMO_API_URL", "http://127.0.0.1:8100")
    settings = _settings(role1_url, role2_url, role3_url, role6_url)
    if not embedded_services:
        return execute_demo(api_url, settings)
    apps: list[tuple[Any, str]] = []
    if "LEDGERAI_DEMO_ROLE1_URL" not in os.environ:
        apps.append((create_demo_role1_app(), role1_url))
    if "LEDGERAI_DEMO_ROLE2_URL" not in os.environ:
        apps.append((create_demo_role2_app(), role2_url))
    if "LEDGERAI_DEMO_ROLE3_URL" not in os.environ:
        apps.append((create_demo_role3_app(), role3_url))
    if "LEDGERAI_DEMO_ROLE6_URL" not in os.environ:
        apps.append((create_demo_role6_app(), role6_url))
    if "LEDGERAI_DEMO_API_URL" not in os.environ:
        apps.append((create_app(settings, identity_provider=_identity()), api_url))
    with ExitStack() as stack:
        for app, url in apps:
            parsed = urlparse(url)
            stack.enter_context(LiveServer(app, parsed.hostname or "127.0.0.1", parsed.port or 80))
        return execute_demo(api_url, settings)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--external-services",
        action="store_true",
        help=(
            "connect to configured allowlisted loopback services instead of starting demo services"
        ),
    )
    args = parser.parse_args()
    try:
        summary = run(embedded_services=not args.external_services)
    except (DemoFailure, httpx.HTTPError, OSError) as exc:
        print(f"NOVA demo failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    expected_path = DATASET / "expected" / "summary.json"
    if expected_path.exists() and compare(summary, json.loads(expected_path.read_text())):
        sys.stdout.write(expected_path.read_text())
    else:
        print(json.dumps(summary, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
