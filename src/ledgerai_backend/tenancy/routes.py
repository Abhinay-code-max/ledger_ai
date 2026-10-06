"""Foundational tenant-scoped endpoints only."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ledgerai_backend.api.dependencies import RequestScope, authorized_scope
from ledgerai_backend.core.errors import ERROR_RESPONSES, ApiError
from ledgerai_backend.tenancy.permissions import PermissionCode, require_permission
from ledgerai_backend.tenancy.repository import TenancyRepository
from ledgerai_backend.tenancy.schemas import (
    LegalEntityList,
    LegalEntityResponse,
    OrganizationList,
    OrganizationResponse,
    PrincipalResponse,
)

router = APIRouter(responses=ERROR_RESPONSES)
Scope = Annotated[RequestScope, Depends(authorized_scope)]


def _repository(scope: RequestScope) -> TenancyRepository:
    context = scope.context
    return TenancyRepository(
        scope.session,
        context.tenant_id,
        context.organization_id,
        context.legal_entity_id,
    )


@router.get("/me", response_model=PrincipalResponse)
async def me(scope: Scope) -> PrincipalResponse:
    context = scope.context
    require_permission(context, PermissionCode.WORKSPACE_READ)
    return PrincipalResponse(
        principal_id=context.principal_id,
        external_subject=context.external_subject,
        tenant_id=context.tenant_id,
        organization_id=context.organization_id,
        legal_entity_id=context.legal_entity_id,
        membership_id=context.membership_id,
        roles=sorted(context.roles),
        permissions=sorted(context.permissions),
    )


@router.get("/organizations", response_model=OrganizationList)
async def organizations(
    scope: Scope,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> OrganizationList:
    require_permission(scope.context, PermissionCode.WORKSPACE_READ)
    items = await _repository(scope).list_organizations(limit=limit, offset=offset)
    return OrganizationList(
        items=[OrganizationResponse.model_validate(item) for item in items],
        limit=limit,
        offset=offset,
    )


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
async def organization(organization_id: UUID, scope: Scope) -> OrganizationResponse:
    require_permission(scope.context, PermissionCode.WORKSPACE_READ)
    item = await _repository(scope).get_organization(organization_id)
    if item is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return OrganizationResponse.model_validate(item)


@router.get("/legal-entities", response_model=LegalEntityList)
async def legal_entities(
    scope: Scope,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> LegalEntityList:
    require_permission(scope.context, PermissionCode.WORKSPACE_READ)
    items = await _repository(scope).list_legal_entities(limit=limit, offset=offset)
    return LegalEntityList(
        items=[LegalEntityResponse.model_validate(item) for item in items],
        limit=limit,
        offset=offset,
    )


@router.get("/legal-entities/{legal_entity_id}", response_model=LegalEntityResponse)
async def legal_entity(legal_entity_id: UUID, scope: Scope) -> LegalEntityResponse:
    require_permission(scope.context, PermissionCode.WORKSPACE_READ)
    item = await _repository(scope).get_legal_entity(legal_entity_id)
    if item is None:
        raise ApiError(404, "AUTHORIZATION", "RESOURCE_NOT_FOUND", "Resource not found.")
    return LegalEntityResponse.model_validate(item)
