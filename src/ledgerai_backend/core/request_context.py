"""Request identifiers and authorization context."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from uuid import UUID, uuid4


def safe_external_id(value: str | None) -> str:
    if value:
        try:
            return str(UUID(value))
        except ValueError:
            pass
    return str(uuid4())


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    principal_id: UUID
    external_subject: str
    tenant_id: UUID
    organization_id: UUID | None
    legal_entity_id: UUID | None
    membership_id: UUID
    roles: frozenset[str]
    permissions: frozenset[str]
    request_id: str
    correlation_id: str


_authorization_context: ContextVar[AuthorizationContext | None] = ContextVar(
    "ledgerai_authorization_context", default=None
)


def set_authorization_context(context: AuthorizationContext) -> Token[AuthorizationContext | None]:
    return _authorization_context.set(context)


def reset_authorization_context(token: Token[AuthorizationContext | None]) -> None:
    _authorization_context.reset(token)


def current_authorization_context() -> AuthorizationContext:
    context = _authorization_context.get()
    if context is None:
        raise RuntimeError("authorization context is unavailable")
    return context
