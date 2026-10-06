"""Strict shared primitives for v1 contracts."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    WithJsonSchema,
    field_serializer,
    field_validator,
    model_validator,
)

SchemaVersion = Literal["1.0"]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
Confidence = Annotated[Decimal, Field(ge=Decimal("0"), le=Decimal("1"))]
NonEmptyString = Annotated[str, StringConstraints(min_length=1)]
VersionToken = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$",
    ),
]

_SCHEMA_SQL_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_SCHEMA_SQL_IDENTIFIER_WITH_UNDERSCORE = r"[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+"
_SCHEMA_SELECT = r"[Ss][Ee][Ll][Ee][Cc][Tt]"
_SCHEMA_FROM = r"[Ff][Rr][Oo][Mm]"
_SCHEMA_SQL_CLAUSE = (
    r"(?:[Ww][Hh][Ee][Rr][Ee]|[Jj][Oo][Ii][Nn]|[Ll][Ii][Mm][Ii][Tt]|"
    r"[Oo][Rr][Dd][Ee][Rr]\s+[Bb][Yy]|[Gg][Rr][Oo][Uu][Pp]\s+[Bb][Yy])"
)
_SCHEMA_RAW_SQL_PATTERN = (
    rf"(?:\b{_SCHEMA_SELECT}\s+(?:\*|"
    rf"{_SCHEMA_SQL_IDENTIFIER}\s*,\s*{_SCHEMA_SQL_IDENTIFIER}"
    rf"(?:\s*,\s*{_SCHEMA_SQL_IDENTIFIER})*|{_SCHEMA_SQL_IDENTIFIER_WITH_UNDERSCORE})"
    rf"\s+{_SCHEMA_FROM}\s+{_SCHEMA_SQL_IDENTIFIER}\b|"
    rf"\b{_SCHEMA_SELECT}\s+{_SCHEMA_SQL_IDENTIFIER}\s+{_SCHEMA_FROM}\s+"
    rf"{_SCHEMA_SQL_IDENTIFIER}\s*(?:;|$)|"
    rf"\b{_SCHEMA_SELECT}\s+{_SCHEMA_SQL_IDENTIFIER}\s+{_SCHEMA_FROM}\s+"
    rf"{_SCHEMA_SQL_IDENTIFIER}\s+{_SCHEMA_SQL_CLAUSE}\b|"
    rf"\b[Ii][Nn][Ss][Ee][Rr][Tt]\s+[Ii][Nn][Tt][Oo]\s+{_SCHEMA_SQL_IDENTIFIER}"
    r"\s*(?:\(|[Vv][Aa][Ll][Uu][Ee][Ss]\b|[Ss][Ee][Ll][Ee][Cc][Tt]\b)|"
    rf"\b[Uu][Pp][Dd][Aa][Tt][Ee]\s+{_SCHEMA_SQL_IDENTIFIER}\s+"
    rf"[Ss][Ee][Tt]\s+{_SCHEMA_SQL_IDENTIFIER}\s*=|"
    rf"\b[Dd][Ee][Ll][Ee][Tt][Ee]\s+{_SCHEMA_FROM}\s+{_SCHEMA_SQL_IDENTIFIER}"
    rf"\s*(?:;|$|[Ww][Hh][Ee][Rr][Ee]\b)|"
    r"\b(?:[Dd][Rr][Oo][Pp]|[Aa][Ll][Tt][Ee][Rr]|[Tt][Rr][Uu][Nn][Cc][Aa][Tt][Ee]|"
    rf"[Cc][Rr][Ee][Aa][Tt][Ee])\s+[Tt][Aa][Bb][Ll][Ee]\s+{_SCHEMA_SQL_IDENTIFIER}\b)"
)
_SAFE_MESSAGE_SCHEMA_PATTERN = (
    r"^(?![\s\S]*(?:Traceback \(most recent call last\)|BEGIN (?:RSA )?PRIVATE KEY|"
    r"(?:postgres(?:ql)?|mysql|mongodb|redis|jdbc):\/\/|Bearer eyJ|ghp_|sk_live_|AKIA|"
    rf"[A-Za-z]:\\|\/(?:etc|var|home|Users|root|tmp)\/|{_SCHEMA_RAW_SQL_PATTERN}))"
    r"[\s\S]{1,1000}$"
)

_SQL_IDENTIFIER = r"[a-z_][a-z0-9_]*"
_SQL_IDENTIFIER_WITH_UNDERSCORE = r"[a-z][a-z0-9]*_[a-z0-9_]+"
_RAW_SQL_RE = re.compile(
    rf"(?:\bselect\s+(?:\*|{_SQL_IDENTIFIER}\s*,\s*{_SQL_IDENTIFIER}"
    rf"(?:\s*,\s*{_SQL_IDENTIFIER})*|{_SQL_IDENTIFIER_WITH_UNDERSCORE})"
    rf"\s+from\s+{_SQL_IDENTIFIER}\b|"
    rf"\bselect\s+{_SQL_IDENTIFIER}\s+from\s+{_SQL_IDENTIFIER}\s*(?:;|$)|"
    rf"\bselect\s+{_SQL_IDENTIFIER}\s+from\s+{_SQL_IDENTIFIER}\s+"
    r"(?:where|join|limit|order\s+by|group\s+by)\b|"
    rf"\binsert\s+into\s+{_SQL_IDENTIFIER}\s*(?:\(|values\b|select\b)|"
    rf"\bupdate\s+{_SQL_IDENTIFIER}\s+set\s+{_SQL_IDENTIFIER}\s*=|"
    rf"\bdelete\s+from\s+{_SQL_IDENTIFIER}\s*(?:;|$|where\b)|"
    rf"\b(?:drop|alter|truncate|create)\s+table\s+{_SQL_IDENTIFIER}\b)",
    flags=re.IGNORECASE,
)


def _validate_safe_message(value: str) -> str:
    lowered = value.lower()
    dangerous_fragments = (
        "traceback (most recent call last)",
        "begin private key",
        "begin rsa private key",
        "postgres://",
        "postgresql://",
        "mysql://",
        "mongodb://",
        "redis://",
        "jdbc:",
        "bearer eyj",
        "ghp_",
        "sk_live_",
        "akia",
    )
    dangerous_patterns = (
        r"[a-z]:\\",
        r"/(?:etc|var|home|users|root|tmp)/",
    )
    if not value.strip() or any(fragment in lowered for fragment in dangerous_fragments):
        raise ValueError("message must contain only user-safe diagnostic text")
    if any(re.search(pattern, lowered, flags=re.DOTALL) for pattern in dangerous_patterns):
        raise ValueError("message must contain only user-safe diagnostic text")
    if _RAW_SQL_RE.search(value):
        raise ValueError("message must contain only user-safe diagnostic text")
    return value


SafeMessage = Annotated[
    str,
    StringConstraints(min_length=1, max_length=1000),
    AfterValidator(_validate_safe_message),
    WithJsonSchema(
        {
            "type": "string",
            "minLength": 1,
            "maxLength": 1000,
            "pattern": _SAFE_MESSAGE_SCHEMA_PATTERN,
            "description": (
                "User-safe text only; runtime middleware must still sanitize exceptions."
            ),
        },
        mode="validation",
    ),
]


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return value.astimezone(UTC)


UtcDateTime = Annotated[datetime, AfterValidator(_aware_utc)]
MoneyDecimal = Annotated[
    Decimal,
    WithJsonSchema(
        {"type": "string", "pattern": r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$"},
        mode="validation",
    ),
]
PositiveMoneyDecimal = Annotated[
    Decimal,
    WithJsonSchema(
        {
            "type": "string",
            "pattern": r"^(?=.*[1-9])(?:0|[1-9]\d*)(?:\.\d+)?$",
        },
        mode="validation",
    ),
]


class ContractModel(BaseModel):
    """Base contract: reject unknown fields and use JSON-safe enum values."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True, validate_assignment=True)


class Money(ContractModel):
    """Exact money. JSON amount is always a decimal string; floats are forbidden."""

    amount: MoneyDecimal
    currency: CurrencyCode

    @field_validator("amount", mode="before")
    @classmethod
    def reject_float_and_ambiguous_types(cls, value: Any) -> Any:
        if isinstance(value, (float, int)):
            raise ValueError("amount must be supplied as a decimal string")
        if not isinstance(value, (str, Decimal)):
            raise ValueError("amount must be supplied as a decimal string")
        if isinstance(value, str) and not re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d+)?", value):
            raise ValueError("amount must be a canonical decimal string")
        return value

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return format(value, "f")


class PositiveMoney(Money):
    """Exact positive money for records whose DEBIT/CREDIT field carries the sign."""

    amount: PositiveMoneyDecimal

    @field_validator("amount")
    @classmethod
    def require_strictly_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("directed money amount must be greater than zero")
        return value


class ProducerType(StrEnum):
    SERVICE = "SERVICE"
    AGENT = "AGENT"
    MODEL = "MODEL"
    RULE_ENGINE = "RULE_ENGINE"
    HUMAN = "HUMAN"


class ProducerMetadata(ContractModel):
    producer_type: ProducerType
    name: NonEmptyString
    version: NonEmptyString
    model_name: str | None = None
    model_version: str | None = None
    algorithm_version: str | None = None
    rule_or_policy_version: str | None = None
    prompt_template_version: str | None = None

    @model_validator(mode="after")
    def require_model_details(self) -> ProducerMetadata:
        if self.producer_type == ProducerType.MODEL and not (
            self.model_name and self.model_version
        ):
            raise ValueError("model producers require model_name and model_version")
        return self


class CorrelationMetadata(ContractModel):
    """Request starts an interaction; correlation spans it; causation identifies its parent."""

    request_id: UUID
    correlation_id: UUID
    causation_id: UUID | None = None


class BoundingBox(ContractModel):
    page: int = Field(ge=1)
    x: Decimal = Field(ge=0)
    y: Decimal = Field(ge=0)
    width: Decimal = Field(gt=0)
    height: Decimal = Field(gt=0)


class ProvenanceReference(ContractModel):
    source_document_id: UUID | None = None
    document_version: NonEmptyString | None = None
    page_number: int | None = Field(default=None, ge=1)
    bounding_box: BoundingBox | None = None
    source_field: str | None = None
    source_row: int | None = Field(default=None, ge=1)
    extraction_version: str | None = None
    confidence: Confidence | None = None
    evidence_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    human_correction_id: UUID | None = None

    @model_validator(mode="after")
    def keep_page_consistent(self) -> ProvenanceReference:
        if self.bounding_box and self.page_number and self.bounding_box.page != self.page_number:
            raise ValueError("bounding box page must match page_number")
        return self


class ResourceReference(ContractModel):
    resource_type: NonEmptyString
    resource_id: UUID
    resource_version: NonEmptyString | None = None


class VersionedResourceReference(ResourceReference):
    """Reference bound to an exact immutable resource version."""

    resource_version: VersionToken


class ActorReference(ContractModel):
    actor_type: Literal["HUMAN", "SERVICE", "AGENT"]
    actor_id: NonEmptyString


class ValidationIssue(ContractModel):
    code: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]+$")]
    message: NonEmptyString
    field: str | None = None
    severity: Literal["INFO", "WARNING", "ERROR"]
