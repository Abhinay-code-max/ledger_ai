"""Infrastructure and cross-role ports used by the Phase 2 domain."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredObject:
    byte_size: int
    content_type: str
    sha256: str
    version_id: str | None = None
    server_side_encryption: str | None = None


class ObjectStoragePort(Protocol):
    def create_upload_url(
        self, *, object_key: str, content_type: str, byte_size: int, expires_seconds: int
    ) -> str: ...

    def stat_object(self, *, object_key: str) -> StoredObject: ...

    def read_object(self, *, object_key: str, maximum_bytes: int) -> bytes: ...


class ScanOutcome(StrEnum):
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"
    SUSPICIOUS = "SUSPICIOUS"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True, slots=True)
class ScanResult:
    outcome: ScanOutcome
    scanner_name: str
    scanner_version: str
    signature_version: str | None
    reason_code: str


class MalwareScannerPort(Protocol):
    def scan(self, content: bytes, *, expected_sha256: str) -> ScanResult: ...


class JobQueuePort(Protocol):
    def enqueue(
        self,
        *,
        job_id: UUID,
        queue_name: str,
        correlation_id: UUID,
        event_id: UUID | None = None,
    ) -> str: ...


class EventPublisherPort(Protocol):
    def publish(
        self, *, event_id: UUID, event_type: str, payload: Mapping[str, object]
    ) -> None: ...


class ClockPort(Protocol):
    def now(self) -> datetime: ...


class Role1DocumentIntelligencePort(Protocol):
    def request_extraction(self, *, document_id: UUID, version_id: UUID) -> str: ...


class Role2FinancialCorePort(Protocol):
    def submit_transactions(self, *, import_id: UUID, transaction_ids: list[UUID]) -> str: ...


class Role3ReconciliationPort(Protocol):
    def request_reconciliation(self, *, transaction_ids: list[UUID]) -> str: ...


class Role6ModelGatewayPort(Protocol):
    def classify(self, *, evidence_reference: str) -> str: ...
