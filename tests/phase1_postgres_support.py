"""Shared synthetic identifiers and opt-in PostgreSQL DSNs for Phase 1 tests."""

import os
from uuid import UUID, uuid5

import pytest

TEST_NAMESPACE = UUID("7169a83a-85b7-46df-b06f-43929e84476e")
ACME_TENANT = uuid5(TEST_NAMESPACE, "acme:tenant")
ACME_ORGANIZATION = uuid5(TEST_NAMESPACE, "acme:organization")
ACME_ENTITY = uuid5(TEST_NAMESPACE, "acme:entity")
ACME_PRINCIPAL = uuid5(TEST_NAMESPACE, "acme:principal")
ACME_MEMBERSHIP = uuid5(TEST_NAMESPACE, "acme:membership")
ACME_ROLE = uuid5(TEST_NAMESPACE, "acme:role")
NO_PERMISSION_PRINCIPAL = uuid5(TEST_NAMESPACE, "nova:no-permission:principal")
NO_PERMISSION_MEMBERSHIP = uuid5(TEST_NAMESPACE, "nova:no-permission:membership")
NO_PERMISSION_ROLE = uuid5(TEST_NAMESPACE, "nova:no-permission:role")


def admin_dsn() -> str:
    value = os.getenv("LEDGERAI_TEST_ADMIN_DSN")
    if not value:
        pytest.skip("LEDGERAI_TEST_ADMIN_DSN is required")
    return value


def runtime_dsn() -> str:
    value = os.getenv("LEDGERAI_TEST_RUNTIME_DSN")
    if not value:
        pytest.skip("LEDGERAI_TEST_RUNTIME_DSN is required")
    return value
