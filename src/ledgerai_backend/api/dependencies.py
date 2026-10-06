"""Authentication, membership bootstrap, and request transaction dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ledgerai_backend.core.errors import ApiError
from ledgerai_backend.core.identity import AuthenticationError, IdentityProviderPort
from ledgerai_backend.core.request_context import (
    AuthorizationContext,
    reset_authorization_context,
    set_authorization_context,
)
from ledgerai_backend.database.rls import (
    assert_database_tenant_context,
    resolve_bootstrap_authorization,
    set_tenant_context,
)

bearer = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class RequestScope:
    context: AuthorizationContext
    session: AsyncSession


async def authorized_scope(
    request: Request,
    workspace_code: Annotated[str, Header(alias="X-Workspace-Code", min_length=1, max_length=80)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
    selected_organization_id: Annotated[UUID | None, Header(alias="X-Organization-ID")] = None,
    selected_legal_entity_id: Annotated[UUID | None, Header(alias="X-Legal-Entity-ID")] = None,
) -> AsyncIterator[RequestScope]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            401, "AUTHENTICATION", "AUTHENTICATION_REQUIRED", "Authentication is required."
        )
    identity_provider: IdentityProviderPort = request.app.state.identity_provider
    try:
        identity = await identity_provider.verify(credentials.credentials)
    except AuthenticationError as exc:
        raise ApiError(401, "AUTHENTICATION", "INVALID_TOKEN", "Authentication failed.") from exc

    session_factory = request.app.state.session_factory
    async with session_factory() as session, session.begin():
        bootstrap = await resolve_bootstrap_authorization(
            session,
            issuer=identity.issuer,
            subject=identity.subject,
            workspace_code=workspace_code,
            organization_id=selected_organization_id,
            legal_entity_id=selected_legal_entity_id,
        )
        if bootstrap is None:
            raise ApiError(
                403, "AUTHORIZATION", "WORKSPACE_ACCESS_DENIED", "Workspace access denied."
            )
        await set_tenant_context(session, bootstrap.tenant_id)
        await assert_database_tenant_context(session, bootstrap.tenant_id)
        context = AuthorizationContext(
            principal_id=bootstrap.principal_id,
            external_subject=identity.subject,
            tenant_id=bootstrap.tenant_id,
            organization_id=bootstrap.organization_id,
            legal_entity_id=bootstrap.legal_entity_id,
            membership_id=bootstrap.membership_id,
            roles=bootstrap.roles,
            permissions=bootstrap.permissions,
            request_id=request.state.request_id,
            correlation_id=request.state.correlation_id,
        )
        token = set_authorization_context(context)
        try:
            yield RequestScope(context=context, session=session)
        finally:
            reset_authorization_context(token)
