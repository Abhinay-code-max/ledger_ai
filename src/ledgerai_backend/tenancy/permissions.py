"""Explicit Phase 1 permissions and authorization checks."""

from enum import StrEnum

from ledgerai_backend.core.errors import ApiError
from ledgerai_backend.core.request_context import AuthorizationContext


class PermissionCode(StrEnum):
    WORKSPACE_READ = "workspace:read"
    WORKSPACE_ADMIN = "workspace:admin"
    MEMBERSHIP_ADMIN = "membership:admin"
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    REVIEW_ACTION = "review:act"
    FINANCIAL_STATEMENT_READ = "financial-statement:read"
    PERIOD_CLOSE_REQUEST = "period-close:request"
    AUDIT_READ = "audit:read"


def require_permission(context: AuthorizationContext, permission: PermissionCode) -> None:
    if permission.value not in context.permissions:
        raise ApiError(403, "AUTHORIZATION", "PERMISSION_DENIED", "Permission is required.")
