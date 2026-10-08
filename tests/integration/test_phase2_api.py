from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from phase1_postgres_support import admin_dsn, runtime_dsn
from pydantic import SecretStr

from ledgerai_backend.adapters.scanner import DeterministicMalwareScanner
from ledgerai_backend.core.config import Settings
from ledgerai_backend.core.identity import DeterministicTestIdentityProvider, VerifiedIdentity
from ledgerai_backend.database.seed import stable_id
from ledgerai_backend.main import create_app
from ledgerai_backend.ports import StoredObject

pytestmark = pytest.mark.postgres
ISSUER = "https://identity.demo.invalid/"


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}
        self.last_key = ""

    def create_upload_url(
        self, *, object_key: str, content_type: str, byte_size: int, expires_seconds: int
    ) -> str:
        self.last_key = object_key
        self.content_types[object_key] = content_type
        assert object_key.startswith("quarantine/")
        assert expires_seconds <= 900
        return "https://storage.invalid/synthetic-upload"

    def stat_object(self, *, object_key: str) -> StoredObject:
        content = self.objects[object_key]
        return StoredObject(
            len(content), self.content_types[object_key], sha256(content).hexdigest()
        )

    def read_object(self, *, object_key: str, maximum_bytes: int) -> bytes:
        content = self.objects[object_key]
        if len(content) > maximum_bytes:
            raise ValueError
        return content


@pytest.fixture
def ingestion_api() -> Iterator[tuple[TestClient, MemoryStorage]]:
    storage = MemoryStorage()
    settings = Settings(
        environment="test",
        allowed_hosts=["testserver"],
        database_dsn=SecretStr(runtime_dsn().replace("postgresql://", "postgresql+psycopg://", 1)),
        scanner_adapter="deterministic",
    )
    identity = DeterministicTestIdentityProvider(
        {
            "nova-admin-token": VerifiedIdentity(ISSUER, "nova-admin"),
            "acme-admin-token": VerifiedIdentity(ISSUER, "acme-admin"),
        }
    )
    with TestClient(
        create_app(
            settings,
            identity_provider=identity,
            object_storage=storage,
            malware_scanner=DeterministicMalwareScanner(),
        )
    ) as client:
        yield client, storage


def headers(
    *, key: str, token: str = "nova-admin-token", workspace: str = "nova"
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Code": workspace,
        "X-Organization-ID": str(stable_id("nova:organization")),
        "X-Legal-Entity-ID": str(stable_id("nova:legal-entity")),
        "Idempotency-Key": key,
    }


def test_clean_document_upload_is_immutable_and_idempotent(
    ingestion_api: tuple[TestClient, MemoryStorage],
) -> None:
    api, storage = ingestion_api
    content = b"%PDF-1.7\nsynthetic evidence"
    body = {
        "original_filename": "../../untrusted.pdf",
        "media_type": "application/pdf",
        "byte_size": len(content),
        "sha256": sha256(content).hexdigest(),
    }
    upload_key = f"upload-{uuid4()}"
    first = api.post("/api/v1/documents/uploads", json=body, headers=headers(key=upload_key))
    second = api.post("/api/v1/documents/uploads", json=body, headers=headers(key=upload_key))
    assert first.status_code == second.status_code == 201
    assert first.json()["document_id"] == second.json()["document_id"]
    assert first.json()["upload_id"] == second.json()["upload_id"]
    assert "quarantine" not in first.text

    storage.objects[storage.last_key] = content
    complete_key = f"complete-{uuid4()}"
    complete = api.post(
        f"/api/v1/documents/uploads/{first.json()['upload_id']}/complete",
        json={"byte_size": len(content), "sha256": sha256(content).hexdigest()},
        headers=headers(key=complete_key),
    )
    repeated = api.post(
        f"/api/v1/documents/uploads/{first.json()['upload_id']}/complete",
        json={"byte_size": len(content), "sha256": sha256(content).hexdigest()},
        headers=headers(key=complete_key),
    )
    assert complete.status_code == repeated.status_code == 200
    assert complete.json()["status"] == "ACCEPTED"
    versions = api.get(
        f"/api/v1/documents/{first.json()['document_id']}/versions",
        headers=headers(key="unused-0001"),
    )
    assert versions.status_code == 200
    assert len(versions.json()) == 1
    assert "object_key" not in versions.text


def test_reupload_creates_an_immutable_next_version(
    ingestion_api: tuple[TestClient, MemoryStorage],
) -> None:
    api, storage = ingestion_api
    document_id: str | None = None
    upload_ids: list[str] = []
    for version_number, content in enumerate(
        (b"%PDF-1.7 first version", b"%PDF-1.7 replacement version"), start=1
    ):
        body: dict[str, object] = {
            "original_filename": "evidence.pdf",
            "media_type": "application/pdf",
            "byte_size": len(content),
            "sha256": sha256(content).hexdigest(),
        }
        if document_id is not None:
            body["document_id"] = document_id
        initiated = api.post(
            "/api/v1/documents/uploads",
            json=body,
            headers=headers(key=f"version-{version_number}-{uuid4()}"),
        )
        assert initiated.status_code == 201
        document_id = initiated.json()["document_id"]
        upload_ids.append(initiated.json()["upload_id"])
        storage.objects[storage.last_key] = content
        completed = api.post(
            f"/api/v1/documents/uploads/{initiated.json()['upload_id']}/complete",
            json={"byte_size": len(content), "sha256": sha256(content).hexdigest()},
            headers=headers(key=f"complete-{version_number}-{uuid4()}"),
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "ACCEPTED"

    assert upload_ids[0] != upload_ids[1]
    versions = api.get(
        f"/api/v1/documents/{document_id}/versions",
        headers=headers(key=f"read-{uuid4()}"),
    )
    assert versions.status_code == 200
    assert [item["version_number"] for item in versions.json()] == [1, 2]
    assert "object_key" not in versions.text


@pytest.mark.parametrize(
    ("filename", "media_type", "content"),
    [
        ("synthetic.jpg", "image/jpeg", b"\xff\xd8\xffsynthetic jpeg"),
        ("synthetic.png", "image/png", b"\x89PNG\r\n\x1a\nsynthetic png"),
    ],
)
def test_supported_image_uploads_are_accepted(
    ingestion_api: tuple[TestClient, MemoryStorage],
    filename: str,
    media_type: str,
    content: bytes,
) -> None:
    api, storage = ingestion_api
    initiated = api.post(
        "/api/v1/documents/uploads",
        json={
            "original_filename": filename,
            "media_type": media_type,
            "byte_size": len(content),
            "sha256": sha256(content).hexdigest(),
        },
        headers=headers(key=f"image-{uuid4()}"),
    )
    assert initiated.status_code == 201
    storage.objects[storage.last_key] = content
    completed = api.post(
        f"/api/v1/documents/uploads/{initiated.json()['upload_id']}/complete",
        json={"byte_size": len(content), "sha256": sha256(content).hexdigest()},
        headers=headers(key=f"complete-{uuid4()}"),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "ACCEPTED"


def test_filename_and_declared_type_mismatch_is_rejected(
    ingestion_api: tuple[TestClient, MemoryStorage],
) -> None:
    api, _ = ingestion_api
    content = b"%PDF-1.7 synthetic"
    response = api.post(
        "/api/v1/documents/uploads",
        json={
            "original_filename": "synthetic.png",
            "media_type": "application/pdf",
            "byte_size": len(content),
            "sha256": sha256(content).hexdigest(),
        },
        headers=headers(key=f"mismatch-{uuid4()}"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "FILENAME_TYPE_MISMATCH"


def test_upload_idempotency_conflict_and_foreign_neutrality(
    ingestion_api: tuple[TestClient, MemoryStorage],
) -> None:
    api, _ = ingestion_api
    content = b"%PDF-1.7\nother synthetic"
    body = {
        "original_filename": "safe.pdf",
        "media_type": "application/pdf",
        "byte_size": len(content),
        "sha256": sha256(content).hexdigest(),
    }
    upload_key = f"upload-{uuid4()}"
    assert (
        api.post(
            "/api/v1/documents/uploads", json=body, headers=headers(key=upload_key)
        ).status_code
        == 201
    )
    body["original_filename"] = "different.pdf"
    conflict = api.post("/api/v1/documents/uploads", json=body, headers=headers(key=upload_key))
    assert conflict.status_code == 409

    foreign_headers = headers(key="foreign-0001", token="acme-admin-token", workspace="acme")
    foreign_headers["X-Organization-ID"] = str(stable_id("nova:organization"))
    response = api.get(f"/api/v1/documents/{uuid4()}", headers=foreign_headers)
    assert response.status_code in {403, 404}
    assert "object_key" not in response.text


def test_expired_idempotency_key_can_start_a_new_operation(
    ingestion_api: tuple[TestClient, MemoryStorage],
) -> None:
    api, _ = ingestion_api
    key = f"expired-{uuid4()}"
    base = {
        "original_filename": "first.pdf",
        "media_type": "application/pdf",
        "byte_size": 10,
        "sha256": "1" * 64,
    }
    first = api.post("/api/v1/documents/uploads", json=base, headers=headers(key=key))
    assert first.status_code == 201
    with psycopg.connect(admin_dsn()) as connection:
        connection.execute(
            "UPDATE idempotency_records SET expires_at=statement_timestamp()-interval '1 second' WHERE idempotency_key=%s",
            (key,),
        )
    base["original_filename"] = "second.pdf"
    second = api.post("/api/v1/documents/uploads", json=base, headers=headers(key=key))
    assert second.status_code == 201
    assert second.json()["document_id"] != first.json()["document_id"]


def test_infected_missing_and_hash_mismatch_never_become_accepted(
    ingestion_api: tuple[TestClient, MemoryStorage],
) -> None:
    api, storage = ingestion_api
    cases = (
        (b"%PDF-1.7 EICAR-STANDARD-ANTIVIRUS-TEST-FILE", None, "REJECTED", "MALWARE"),
        (
            b"%PDF-1.7 LEDGERAI-SUSPICIOUS",
            None,
            "REJECTED",
            "SUSPICIOUS_CONTENT",
        ),
        (
            b"%PDF-1.7 LEDGERAI-SCANNER-UNAVAILABLE",
            None,
            "QUARANTINED",
            "SCAN_UNAVAILABLE",
        ),
        (
            b"%PDF-1.7 LEDGERAI-SCANNER-ERROR",
            None,
            "QUARANTINED",
            "SCAN_ERROR",
        ),
        (
            b"%PDF-1.7 LEDGERAI-SCANNER-TIMEOUT",
            None,
            "QUARANTINED",
            "SCAN_TIMEOUT",
        ),
        (b"%PDF-1.7 missing", b"", "FAILED", "STORAGE_OBJECT_UNAVAILABLE"),
        (b"%PDF-1.7 expected", b"%PDF-1.7 changed!", "FAILED", "UPLOAD_INTEGRITY_FAILED"),
    )
    for expected, stored, status, failure_code in cases:
        initiated = api.post(
            "/api/v1/documents/uploads",
            json={
                "original_filename": "synthetic.pdf",
                "media_type": "application/pdf",
                "byte_size": len(expected),
                "sha256": sha256(expected).hexdigest(),
            },
            headers=headers(key=f"upload-{uuid4()}"),
        )
        assert initiated.status_code == 201
        if stored is None:
            storage.objects[storage.last_key] = expected
        elif stored:
            storage.objects[storage.last_key] = stored
        completed = api.post(
            f"/api/v1/documents/uploads/{initiated.json()['upload_id']}/complete",
            json={"byte_size": len(expected), "sha256": sha256(expected).hexdigest()},
            headers=headers(key=f"complete-{uuid4()}"),
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == status
        versions = api.get(
            f"/api/v1/documents/{initiated.json()['document_id']}/versions",
            headers=headers(key=f"read-{uuid4()}"),
        )
        assert versions.json()[0]["failure_code"] == failure_code


def test_concurrent_completion_has_one_effective_transition(
    ingestion_api: tuple[TestClient, MemoryStorage],
) -> None:
    api, storage = ingestion_api
    content = b"%PDF-1.7 concurrent synthetic evidence"
    initiated = api.post(
        "/api/v1/documents/uploads",
        json={
            "original_filename": "concurrent.pdf",
            "media_type": "application/pdf",
            "byte_size": len(content),
            "sha256": sha256(content).hexdigest(),
        },
        headers=headers(key=f"upload-{uuid4()}"),
    )
    storage.objects[storage.last_key] = content
    completion_headers = headers(key=f"complete-{uuid4()}")

    def complete() -> int:
        return int(
            api.post(
                f"/api/v1/documents/uploads/{initiated.json()['upload_id']}/complete",
                json={"byte_size": len(content), "sha256": sha256(content).hexdigest()},
                headers=completion_headers,
            ).status_code
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(lambda _: complete(), range(2))) == [200, 200]
    versions = api.get(
        f"/api/v1/documents/{initiated.json()['document_id']}/versions",
        headers=headers(key=f"read-{uuid4()}"),
    )
    assert versions.json()[0]["status"] == "ACCEPTED"


def test_transient_storage_failure_retries_with_the_same_idempotency_key(
    ingestion_api: tuple[TestClient, MemoryStorage],
) -> None:
    api, storage = ingestion_api
    content = b"%PDF-1.7 retryable synthetic evidence"
    initiated = api.post(
        "/api/v1/documents/uploads",
        json={
            "original_filename": "retryable.pdf",
            "media_type": "application/pdf",
            "byte_size": len(content),
            "sha256": sha256(content).hexdigest(),
        },
        headers=headers(key=f"upload-{uuid4()}"),
    )
    complete_headers = headers(key=f"complete-{uuid4()}")
    first = api.post(
        f"/api/v1/documents/uploads/{initiated.json()['upload_id']}/complete",
        json={"byte_size": len(content), "sha256": sha256(content).hexdigest()},
        headers=complete_headers,
    )
    assert first.status_code == 200
    assert first.json()["status"] == "FAILED"

    storage.objects[storage.last_key] = content
    retried = api.post(
        f"/api/v1/documents/uploads/{initiated.json()['upload_id']}/complete",
        json={"byte_size": len(content), "sha256": sha256(content).hexdigest()},
        headers=complete_headers,
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "ACCEPTED"


def test_csv_import_partial_success_and_duplicate_request(
    ingestion_api: tuple[TestClient, MemoryStorage],
) -> None:
    api, _ = ingestion_api
    import_marker = uuid4()
    csv_content = (
        b"booking_date,amount,currency,direction,narration\n"
        + f"2026-10-01,125.50,INR,DEBIT,Synthetic {import_marker}\n".encode()
        + b"invalid,1.00,INR,CREDIT,Rejected row\n"
    )
    request_headers = headers(key=f"csv-import-{uuid4()}")
    bank_account_id = uuid4()
    first = api.post(
        "/api/v1/transaction-imports",
        headers=request_headers,
        data={"bank_account_id": str(bank_account_id), "mapping_json": "{}"},
        files={"file": ("synthetic.csv", csv_content, "text/csv")},
    )
    second = api.post(
        "/api/v1/transaction-imports",
        headers=request_headers,
        data={"bank_account_id": str(bank_account_id), "mapping_json": "{}"},
        files={"file": ("synthetic.csv", csv_content, "text/csv")},
    )
    duplicate_with_new_key = api.post(
        "/api/v1/transaction-imports",
        headers=headers(key=f"csv-import-{uuid4()}"),
        data={"bank_account_id": str(bank_account_id), "mapping_json": "{}"},
        files={"file": ("renamed.csv", csv_content, "text/csv")},
    )
    assert first.status_code == second.status_code == duplicate_with_new_key.status_code == 201
    assert first.json()["id"] == second.json()["id"] == duplicate_with_new_key.json()["id"]
    assert first.json()["status"] == "PARTIAL"
    assert first.json()["accepted_count"] == first.json()["rejected_count"] == 1
    errors = api.get(
        f"/api/v1/transaction-imports/{first.json()['id']}/errors",
        headers=request_headers,
    )
    assert errors.status_code == 200
    assert errors.json()[0]["error_code"] == "INVALID_ROW"
    transactions = api.get(
        f"/api/v1/transactions?import_id={first.json()['id']}&limit=10",
        headers=request_headers,
    )
    assert transactions.status_code == 200
    assert any(item["import_id"] == first.json()["id"] for item in transactions.json()["items"])


def test_transaction_import_filter_uses_stable_keyset_pagination(
    ingestion_api: tuple[TestClient, MemoryStorage],
) -> None:
    api, _ = ingestion_api
    bank_account_id = uuid4()
    csv_content = b"booking_date,amount,currency,direction,narration\n" + b"".join(
        f"2026-10-01,{row}.00,INR,DEBIT,Synthetic page {row}\n".encode() for row in range(1, 13)
    )
    created = api.post(
        "/api/v1/transaction-imports",
        headers=headers(key=f"csv-pages-{uuid4()}"),
        data={"bank_account_id": str(bank_account_id), "mapping_json": "{}"},
        files={"file": ("pages.csv", csv_content, "text/csv")},
    )
    assert created.status_code == 201
    import_id = created.json()["id"]

    seen: list[str] = []
    after: str | None = None
    while True:
        query = f"/api/v1/transactions?import_id={import_id}&limit=5"
        if after is not None:
            query += f"&after={after}"
        page = api.get(query, headers=headers(key=f"read-pages-{uuid4()}"))
        assert page.status_code == 200
        body = page.json()
        seen.extend(item["id"] for item in body["items"])
        after = body["next_cursor"]
        if after is None:
            break

    assert len(seen) == 12
    assert len(set(seen)) == 12
    assert seen == sorted(seen)
