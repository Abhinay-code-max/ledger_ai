"""Public API schemas for the Phase 1 workspace surface."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PrincipalResponse(ApiModel):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "principal_id": "8d5cf6ae-1ab9-4eec-bf21-301410977a84",
                    "external_subject": "nova-viewer",
                    "tenant_id": "d68afd72-2d24-4cb6-bbf6-c43be4bf98ce",
                    "organization_id": None,
                    "legal_entity_id": None,
                    "membership_id": "0dcd55a4-961f-4d4c-b24a-019b0b3fa263",
                    "roles": ["viewer"],
                    "permissions": ["workspace:read"],
                }
            ]
        },
    )
    principal_id: UUID
    external_subject: str
    tenant_id: UUID
    organization_id: UUID | None
    legal_entity_id: UUID | None
    membership_id: UUID
    roles: list[str]
    permissions: list[str]


class OrganizationResponse(ApiModel):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "4a96e446-dd4e-4fab-9f83-13aac3e4b9d8",
                    "tenant_id": "d68afd72-2d24-4cb6-bbf6-c43be4bf98ce",
                    "name": "NOVA Technologies",
                    "code": "nova-india",
                    "status": "ACTIVE",
                    "version": 1,
                }
            ]
        },
    )
    id: UUID
    tenant_id: UUID
    name: str
    code: str
    status: str
    version: int


class LegalEntityResponse(ApiModel):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "eb19155e-cd20-4e5c-b900-1c1726a1004b",
                    "tenant_id": "d68afd72-2d24-4cb6-bbf6-c43be4bf98ce",
                    "organization_id": "4a96e446-dd4e-4fab-9f83-13aac3e4b9d8",
                    "legal_name": "NOVA TECHNOLOGIES PVT LTD",
                    "display_name": "NOVA Technologies India",
                    "code": "nova-technologies-in",
                    "country_code": "IN",
                    "status": "ACTIVE",
                    "version": 1,
                }
            ]
        },
    )
    id: UUID
    tenant_id: UUID
    organization_id: UUID
    legal_name: str
    display_name: str
    code: str
    country_code: str
    status: str
    version: int


class OrganizationList(ApiModel):
    items: list[OrganizationResponse]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class LegalEntityList(ApiModel):
    items: list[LegalEntityResponse]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
