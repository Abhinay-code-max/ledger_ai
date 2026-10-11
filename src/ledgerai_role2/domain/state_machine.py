"""Posting operation state machine and idempotency transitions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from ledgerai_contracts.v1.common import ValidationIssue


class PostingState(StrEnum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    IN_PROGRESS = "IN_PROGRESS"
    POSTED = "POSTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


def compute_payload_hash(payload: Mapping[str, Any] | object) -> str:
    """Canonical SHA256 hash of request payload for idempotency verification."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class IdempotencyConflictError(Exception):
    """Raised when an operation ID is reused with a different payload."""

    def __init__(self, operation_id: UUID, message: str = "Idempotency conflict") -> None:
        super().__init__(message)
        self.operation_id = operation_id


@dataclass(slots=True)
class PostingOperationRecord:
    operation_id: UUID
    tenant_id: UUID
    organization_id: UUID
    legal_entity_id: UUID
    proposal_id: UUID
    proposal_version: int
    accounting_period_id: UUID
    request_hash: str
    state: PostingState
    posted_journal_id: str | None = None
    posted_at: datetime | None = None
    issues: list[ValidationIssue] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    version: int = 1

    def verify_payload_match(self, incoming_hash: str) -> None:
        """Enforce that the same operation_id must have the identical payload."""
        if self.request_hash != incoming_hash:
            msg = f"Operation '{self.operation_id}' was submitted with a different payload"
            raise IdempotencyConflictError(self.operation_id, msg)
