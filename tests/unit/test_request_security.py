import json
import logging
from uuid import uuid4

import pytest

from ledgerai_backend.core.errors import ApiError
from ledgerai_backend.core.logging import JsonFormatter, redact
from ledgerai_backend.core.request_context import AuthorizationContext, safe_external_id
from ledgerai_backend.tenancy.permissions import PermissionCode, require_permission


def context(*permissions: str) -> AuthorizationContext:
    return AuthorizationContext(
        principal_id=uuid4(),
        external_subject="synthetic",
        tenant_id=uuid4(),
        organization_id=None,
        legal_entity_id=None,
        membership_id=uuid4(),
        roles=frozenset({"viewer"}),
        permissions=frozenset(permissions),
        request_id=str(uuid4()),
        correlation_id=str(uuid4()),
    )


def test_request_id_accepts_only_uuid() -> None:
    supplied = str(uuid4())
    assert safe_external_id(supplied) == supplied
    assert safe_external_id("unsafe header value") != "unsafe header value"


def test_permission_evaluation() -> None:
    require_permission(context("workspace:read"), PermissionCode.WORKSPACE_READ)
    with pytest.raises(ApiError) as error:
        require_permission(context(), PermissionCode.WORKSPACE_READ)
    assert error.value.status_code == 403


def test_recursive_log_redaction() -> None:
    assert redact({"authorization": "Bearer synthetic", "nested": {"password": "x"}}) == {
        "authorization": "[REDACTED]",
        "nested": {"password": "[REDACTED]"},
    }


def test_json_formatter_never_emits_sensitive_fields() -> None:
    record = logging.LogRecord("test", logging.INFO, "", 1, "safe", (), None)
    record.fields = {"token": "synthetic-token", "request_id": "safe-id"}
    rendered = json.loads(JsonFormatter().format(record))
    assert rendered["token"] == "[REDACTED]"
    assert rendered["request_id"] == "safe-id"
