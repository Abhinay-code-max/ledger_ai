"""Infrastructure-neutral asynchronous processing job state."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, GetJsonSchemaHandler, model_validator
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from ledgerai_contracts.v1.common import (
    ContractModel,
    CorrelationMetadata,
    ResourceReference,
    SafeMessage,
    SchemaVersion,
    UtcDateTime,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext

JobState = Literal[
    "QUEUED",
    "PROCESSING",
    "RETRY_SCHEDULED",
    "REVIEW_REQUIRED",
    "COMPLETED",
    "FAILED",
    "DEAD_LETTERED",
]


class ProcessingJob(ContractModel):
    schema_version: SchemaVersion
    job_id: UUID
    tenant_context: EntityTenantContext
    job_type: str = Field(min_length=1)
    state: JobState
    attempt_number: int = Field(ge=0)
    maximum_attempts: int = Field(ge=1)
    input_references: list[ResourceReference] = Field(min_length=1)
    output_references: list[ResourceReference] = Field(default_factory=list)
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    retryable: bool | None = None
    error_code: str | None = None
    safe_error_message: SafeMessage | None = None
    queue_name: str | None = None
    scheduled_for: UtcDateTime | None = None
    correlation: CorrelationMetadata
    created_at: UtcDateTime
    started_at: UtcDateTime | None = None
    updated_at: UtcDateTime
    completed_at: UtcDateTime | None = None
    retry_at: UtcDateTime | None = None
    failed_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def validate_state_details(self) -> ProcessingJob:
        if self.attempt_number > self.maximum_attempts:
            raise ValueError("attempt_number cannot exceed maximum_attempts")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("started_at cannot precede created_at")
        if self.completed_at is not None and (
            self.started_at is None or self.completed_at < self.started_at
        ):
            raise ValueError("completed_at requires and cannot precede started_at")
        if self.failed_at is not None and (
            self.started_at is None or self.failed_at < self.started_at
        ):
            raise ValueError("failed_at requires and cannot precede started_at")
        retry_baseline = self.failed_at or self.updated_at
        if self.retry_at is not None and self.retry_at <= retry_baseline:
            raise ValueError("retry_at must be after the failed or updated attempt time")

        has_error = self.error_code is not None or self.safe_error_message is not None
        if (self.error_code is None) != (self.safe_error_message is None):
            raise ValueError("error_code and safe_error_message must be supplied together")

        if self.state == "QUEUED":
            if (
                any((self.started_at, self.completed_at, self.failed_at, self.retry_at))
                or has_error
            ):
                raise ValueError("QUEUED cannot carry active or terminal processing metadata")
        elif self.state == "PROCESSING":
            if self.started_at is None:
                raise ValueError("PROCESSING requires started_at")
            if any((self.completed_at, self.failed_at, self.retry_at)) or has_error:
                raise ValueError("PROCESSING cannot carry retry or terminal metadata")
        elif self.state == "RETRY_SCHEDULED":
            if self.retry_at is None:
                raise ValueError("RETRY_SCHEDULED requires retry_at")
            if self.started_at is None or self.failed_at is None or not has_error:
                raise ValueError("RETRY_SCHEDULED requires failed-attempt metadata")
            if self.retryable is not True:
                raise ValueError("RETRY_SCHEDULED requires retryable=true")
            if self.attempt_number >= self.maximum_attempts:
                raise ValueError("RETRY_SCHEDULED requires remaining attempts")
            if self.completed_at is not None:
                raise ValueError("RETRY_SCHEDULED cannot carry completion metadata")
        elif self.state == "REVIEW_REQUIRED":
            if self.started_at is None:
                raise ValueError("REVIEW_REQUIRED requires started_at")
            if any((self.completed_at, self.failed_at, self.retry_at)):
                raise ValueError("REVIEW_REQUIRED cannot carry terminal or retry timestamps")
        elif self.state == "COMPLETED":
            if self.started_at is None or self.completed_at is None:
                raise ValueError("COMPLETED requires completed_at and started_at")
            if any((self.failed_at, self.retry_at)) or has_error:
                raise ValueError("COMPLETED cannot carry active error or retry metadata")
        elif self.state == "FAILED":
            if self.started_at is None or self.failed_at is None or not has_error:
                raise ValueError("failed states require error_code, message, and failure time")
            if self.completed_at is not None or self.retry_at is not None:
                raise ValueError("FAILED cannot carry completion or scheduled-retry metadata")
        elif self.state == "DEAD_LETTERED":
            if self.started_at is None or self.failed_at is None or not has_error:
                raise ValueError("failed states require error_code, message, and failure time")
            if self.retryable is not False:
                raise ValueError("DEAD_LETTERED cannot be retryable")
            if self.attempt_number != self.maximum_attempts:
                raise ValueError("DEAD_LETTERED requires attempts to be exhausted")
            if self.completed_at is not None or self.retry_at is not None:
                raise ValueError("DEAD_LETTERED cannot carry completion or retry metadata")
        return self

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        schema = handler(core_schema)
        timestamp = {"type": "string", "format": "date-time"}
        text = {"type": "string", "minLength": 1}

        def state_rule(
            state: str, properties: dict[str, object], required: list[str]
        ) -> dict[str, object]:
            return {
                "if": {
                    "properties": {"state": {"const": state}},
                    "required": ["state"],
                },
                "then": {"properties": properties, "required": required},
            }

        terminal_nulls = {
            "completed_at": {"type": "null"},
            "failed_at": {"type": "null"},
            "retry_at": {"type": "null"},
        }
        error_nulls = {
            "error_code": {"type": "null"},
            "safe_error_message": {"type": "null"},
        }
        schema["allOf"] = [
            state_rule(
                "QUEUED",
                {"started_at": {"type": "null"}, **terminal_nulls, **error_nulls},
                [],
            ),
            state_rule(
                "PROCESSING",
                {"started_at": timestamp, **terminal_nulls, **error_nulls},
                ["started_at"],
            ),
            state_rule(
                "RETRY_SCHEDULED",
                {
                    "started_at": timestamp,
                    "failed_at": timestamp,
                    "retry_at": timestamp,
                    "retryable": {"const": True},
                    "error_code": text,
                    "safe_error_message": text,
                    "completed_at": {"type": "null"},
                },
                [
                    "started_at",
                    "failed_at",
                    "retry_at",
                    "retryable",
                    "error_code",
                    "safe_error_message",
                ],
            ),
            state_rule(
                "REVIEW_REQUIRED",
                {"started_at": timestamp, **terminal_nulls},
                ["started_at"],
            ),
            state_rule(
                "COMPLETED",
                {
                    "started_at": timestamp,
                    "completed_at": timestamp,
                    "failed_at": {"type": "null"},
                    "retry_at": {"type": "null"},
                    **error_nulls,
                },
                ["started_at", "completed_at"],
            ),
            state_rule(
                "FAILED",
                {
                    "started_at": timestamp,
                    "failed_at": timestamp,
                    "error_code": text,
                    "safe_error_message": text,
                    "completed_at": {"type": "null"},
                    "retry_at": {"type": "null"},
                },
                ["started_at", "failed_at", "error_code", "safe_error_message"],
            ),
            state_rule(
                "DEAD_LETTERED",
                {
                    "started_at": timestamp,
                    "failed_at": timestamp,
                    "retryable": {"const": False},
                    "error_code": text,
                    "safe_error_message": text,
                    "completed_at": {"type": "null"},
                    "retry_at": {"type": "null"},
                },
                [
                    "started_at",
                    "failed_at",
                    "retryable",
                    "error_code",
                    "safe_error_message",
                ],
            ),
        ]
        schema["x-ledgerai-pydantic-invariants"] = [
            "attempt_number must not exceed maximum_attempts",
            "DEAD_LETTERED requires attempt_number equal to maximum_attempts",
            "timestamps must follow created/start/update/failure/completion ordering",
            "retry_at must be later than the failed or updated attempt",
        ]
        return schema
