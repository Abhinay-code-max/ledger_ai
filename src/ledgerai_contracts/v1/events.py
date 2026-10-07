"""Versioned domain-event envelope and initial v1 payload types."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar, Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic.json_schema import (
    DEFAULT_REF_TEMPLATE,
    GenerateJsonSchema,
    JsonSchemaMode,
    JsonSchemaValue,
)

from ledgerai_contracts.v1.approvals import ApprovalDecision
from ledgerai_contracts.v1.common import (
    ContractModel,
    ProducerMetadata,
    ResourceReference,
    SafeMessage,
    SchemaVersion,
    UtcDateTime,
)
from ledgerai_contracts.v1.documents import DocumentExtraction, DocumentMetadata
from ledgerai_contracts.v1.exceptions import ExceptionRecord
from ledgerai_contracts.v1.journals import JournalProposal
from ledgerai_contracts.v1.policy import PolicyDecision
from ledgerai_contracts.v1.reconciliation import MatchProposal
from ledgerai_contracts.v1.tenancy import EntityTenantContext


class ResourceEventPayload(ContractModel):
    resource: ResourceReference


class DocumentUploadedPayload(ContractModel):
    document: DocumentMetadata


class ExtractionRequestedPayload(ContractModel):
    document: ResourceReference
    job: ResourceReference


class DocumentExtractedPayload(ContractModel):
    extraction: DocumentExtraction


class TransactionsImportedPayload(ContractModel):
    import_batch: ResourceReference
    transaction_count: int = Field(ge=0)


class ReconciliationRequestedPayload(ContractModel):
    request: ResourceReference
    transaction_ids: list[UUID] = Field(min_length=1)


class ReconciliationProposedPayload(ContractModel):
    proposal: MatchProposal


class ExceptionCreatedPayload(ContractModel):
    exception: ExceptionRecord


class JournalProposalCreatedPayload(ContractModel):
    proposal: JournalProposal


class PolicyEvaluatedPayload(ContractModel):
    decision: PolicyDecision


class ApprovalRequestedPayload(ContractModel):
    approval_request: ResourceReference
    subject: ResourceReference


class ApprovalDecidedPayload(ContractModel):
    decision: ApprovalDecision


class WorkflowFailedPayload(ContractModel):
    workflow: ResourceReference
    error_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    safe_message: SafeMessage
    retryable: bool


EventPayload = (
    ResourceEventPayload
    | DocumentUploadedPayload
    | ExtractionRequestedPayload
    | DocumentExtractedPayload
    | TransactionsImportedPayload
    | ReconciliationRequestedPayload
    | ReconciliationProposedPayload
    | ExceptionCreatedPayload
    | JournalProposalCreatedPayload
    | PolicyEvaluatedPayload
    | ApprovalRequestedPayload
    | ApprovalDecidedPayload
    | WorkflowFailedPayload
)

TenantGetter = Callable[[EventPayload], EntityTenantContext]


@dataclass(frozen=True)
class EventSpec:
    payload_model: type[ContractModel]
    tenant_getter: TenantGetter | None


def _document_uploaded_tenant(payload: EventPayload) -> EntityTenantContext:
    assert isinstance(payload, DocumentUploadedPayload)
    return payload.document.tenant_context


def _document_extracted_tenant(payload: EventPayload) -> EntityTenantContext:
    assert isinstance(payload, DocumentExtractedPayload)
    return payload.extraction.tenant_context


def _reconciliation_proposed_tenant(payload: EventPayload) -> EntityTenantContext:
    assert isinstance(payload, ReconciliationProposedPayload)
    return payload.proposal.tenant_context


def _exception_created_tenant(payload: EventPayload) -> EntityTenantContext:
    assert isinstance(payload, ExceptionCreatedPayload)
    return payload.exception.tenant_context


def _journal_proposal_tenant(payload: EventPayload) -> EntityTenantContext:
    assert isinstance(payload, JournalProposalCreatedPayload)
    return payload.proposal.tenant_context


def _policy_evaluated_tenant(payload: EventPayload) -> EntityTenantContext:
    assert isinstance(payload, PolicyEvaluatedPayload)
    return payload.decision.tenant_context


def _approval_decided_tenant(payload: EventPayload) -> EntityTenantContext:
    assert isinstance(payload, ApprovalDecidedPayload)
    return payload.decision.tenant_context


# Canonical registry for Python parsing, generated schema branches, fixtures, and documentation.
# A None tenant_getter means the typed payload contains immutable resource references only; in that
# case the entity-scoped envelope is authoritative. No initial v1 event is organization-scoped.
EVENT_REGISTRY: dict[str, EventSpec] = {
    "document.uploaded.v1": EventSpec(DocumentUploadedPayload, _document_uploaded_tenant),
    "document.extraction.requested.v1": EventSpec(ExtractionRequestedPayload, None),
    "document.extracted.v1": EventSpec(DocumentExtractedPayload, _document_extracted_tenant),
    "document.validated.v1": EventSpec(ResourceEventPayload, None),
    "transactions.imported.v1": EventSpec(TransactionsImportedPayload, None),
    "reconciliation.requested.v1": EventSpec(ReconciliationRequestedPayload, None),
    "reconciliation.proposed.v1": EventSpec(
        ReconciliationProposedPayload, _reconciliation_proposed_tenant
    ),
    "exception.created.v1": EventSpec(ExceptionCreatedPayload, _exception_created_tenant),
    "journal.proposal.created.v1": EventSpec(
        JournalProposalCreatedPayload, _journal_proposal_tenant
    ),
    "policy.evaluated.v1": EventSpec(PolicyEvaluatedPayload, _policy_evaluated_tenant),
    "approval.requested.v1": EventSpec(ApprovalRequestedPayload, None),
    "approval.decided.v1": EventSpec(ApprovalDecidedPayload, _approval_decided_tenant),
    "journal.posting.requested.v1": EventSpec(ResourceEventPayload, None),
    "journal.posted.v1": EventSpec(ResourceEventPayload, None),
    "period.close.requested.v1": EventSpec(ResourceEventPayload, None),
    "period.closed.v1": EventSpec(ResourceEventPayload, None),
    "workflow.failed.v1": EventSpec(WorkflowFailedPayload, None),
}

EventType = str


class EventEnvelope(ContractModel):
    event_id: UUID
    event_type: EventType = Field(min_length=1)
    schema_version: SchemaVersion
    occurred_at: UtcDateTime
    tenant_context: EntityTenantContext
    correlation_id: UUID
    causation_id: UUID | None = None
    producer: ProducerMetadata
    payload: EventPayload | None = None
    payload_reference: ResourceReference | None = None
    trace_context: dict[str, str] | None = None

    # Backward-compatible read-only view derived from the canonical registry.
    PAYLOAD_MODELS: ClassVar[Mapping[str, type[ContractModel]]] = MappingProxyType(
        {event_type: spec.payload_model for event_type, spec in EVENT_REGISTRY.items()}
    )

    @model_validator(mode="before")
    @classmethod
    def bind_payload_to_event_type(cls, data: Any) -> Any:
        if isinstance(data, dict):
            event_type = data.get("event_type")
            if not isinstance(event_type, str) or event_type not in EVENT_REGISTRY:
                raise ValueError("unsupported event_type")
            if data.get("payload") is not None:
                data = dict(data)
                data["payload"] = EVENT_REGISTRY[event_type].payload_model.model_validate(
                    data["payload"]
                )
        return data

    @model_validator(mode="after")
    def require_exact_payload_choice(self) -> EventEnvelope:
        if (self.payload is None) == (self.payload_reference is None):
            raise ValueError("provide exactly one of payload or payload_reference")
        if self.payload is not None:
            spec = EVENT_REGISTRY[self.event_type]
            expected = spec.payload_model
            if type(self.payload) is not expected:
                raise ValueError(f"{self.event_type} requires {expected.__name__}")
            if spec.tenant_getter is not None:
                payload_tenant = spec.tenant_getter(self.payload)
                if payload_tenant != self.tenant_context:
                    raise ValueError(
                        "event payload tenant context must match envelope tenant context"
                    )
        return self

    @classmethod
    def model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = "validation",
        *,
        union_format: Literal["any_of", "primitive_type_array"] = "any_of",
    ) -> JsonSchemaValue:
        schema = super().model_json_schema(
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
            union_format=union_format,
        )
        variants: list[dict[str, object]] = []
        tenant_paths: dict[str, str] = {}
        for event_type, spec in EVENT_REGISTRY.items():
            typed_payload = {
                "properties": {
                    "event_type": {"const": event_type},
                    "payload": {"$ref": f"#/$defs/{spec.payload_model.__name__}"},
                    "payload_reference": {"type": "null"},
                },
                "required": ["event_type", "payload"],
            }
            referenced_payload = {
                "properties": {
                    "event_type": {"const": event_type},
                    "payload": {"type": "null"},
                    "payload_reference": {"$ref": "#/$defs/ResourceReference"},
                },
                "required": ["event_type", "payload_reference"],
            }
            variants.append({"oneOf": [typed_payload, referenced_payload]})
            tenant_paths[event_type] = (
                "typed payload tenant must equal envelope tenant_context"
                if spec.tenant_getter is not None
                else "envelope tenant_context is authoritative; payload contains references only"
            )
        schema["oneOf"] = variants
        schema["x-ledgerai-tenant-context-invariant"] = {
            "enforcement": (
                "Pydantic typed validation; JSON Schema cannot compare UUID values across paths"
            ),
            "organization_scoped_events": [],
            "event_rules": tenant_paths,
        }
        return schema
