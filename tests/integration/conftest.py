from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from uuid import uuid5

import psycopg
import pytest
import pytest_asyncio
from phase1_postgres_support import (
    ACME_ENTITY,
    ACME_MEMBERSHIP,
    ACME_ORGANIZATION,
    ACME_PRINCIPAL,
    ACME_ROLE,
    ACME_TENANT,
    NO_PERMISSION_MEMBERSHIP,
    NO_PERMISSION_PRINCIPAL,
    NO_PERMISSION_ROLE,
    TEST_NAMESPACE,
    admin_dsn,
    runtime_dsn,
)
from psycopg import Connection
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine

from ledgerai_backend.core.config import Settings
from ledgerai_backend.database.engine import create_engine
from ledgerai_backend.database.seed import seed, stable_id


@pytest.fixture(scope="session", autouse=True)
def postgres_seed() -> Iterator[None]:
    migration_dsn = admin_dsn().replace("postgresql://", "postgresql+psycopg://", 1)
    seed(Settings(environment="test", migration_dsn=SecretStr(migration_dsn)))
    nova_tenant = stable_id("nova:tenant")
    with psycopg.connect(admin_dsn()) as connection:
        connection.execute(
            "INSERT INTO tenants (id, name, code, status) VALUES (%s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (
                ACME_TENANT,
                "ACME SYNTHETIC TENANT",
                "acme",
            ),
        )
        connection.execute(
            "INSERT INTO organizations (id, tenant_id, name, code, status) VALUES (%s, %s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (ACME_ORGANIZATION, ACME_TENANT, "ACME Synthetic", "acme-global"),
        )
        connection.execute(
            """INSERT INTO legal_entities
               (id, tenant_id, organization_id, legal_name, display_name, code, country_code, status)
               VALUES (%s, %s, %s, %s, %s, %s, 'US', 'ACTIVE') ON CONFLICT (id) DO NOTHING""",
            (ACME_ENTITY, ACME_TENANT, ACME_ORGANIZATION, "ACME SYNTHETIC LLC", "ACME", "acme-us"),
        )
        connection.execute(
            "INSERT INTO principals (id, issuer, external_subject, display_name, status) VALUES (%s, %s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (
                ACME_PRINCIPAL,
                "https://identity.demo.invalid/",
                "acme-admin",
                "ACME Synthetic Admin",
            ),
        )
        connection.execute(
            "INSERT INTO memberships (id, tenant_id, principal_id, status) VALUES (%s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (ACME_MEMBERSHIP, ACME_TENANT, ACME_PRINCIPAL),
        )
        connection.execute(
            "INSERT INTO roles (id, tenant_id, code, name) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (ACME_ROLE, ACME_TENANT, "tenant-administrator", "Tenant Administrator"),
        )
        connection.execute(
            "INSERT INTO role_permissions (tenant_id, role_id, permission_code) VALUES (%s, %s, 'workspace:read') ON CONFLICT DO NOTHING",
            (ACME_TENANT, ACME_ROLE),
        )
        connection.execute(
            "INSERT INTO role_assignments (id, tenant_id, membership_id, role_id) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (uuid5(TEST_NAMESPACE, "acme:assignment"), ACME_TENANT, ACME_MEMBERSHIP, ACME_ROLE),
        )
        connection.execute(
            "INSERT INTO principals (id, issuer, external_subject, display_name, status) VALUES (%s, %s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (
                NO_PERMISSION_PRINCIPAL,
                "https://identity.demo.invalid/",
                "nova-no-permission",
                "NOVA No Permission",
            ),
        )
        connection.execute(
            "INSERT INTO memberships (id, tenant_id, principal_id, status) VALUES (%s, %s, %s, 'ACTIVE') ON CONFLICT (id) DO NOTHING",
            (NO_PERMISSION_MEMBERSHIP, nova_tenant, NO_PERMISSION_PRINCIPAL),
        )
        connection.execute(
            "INSERT INTO roles (id, tenant_id, code, name) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (NO_PERMISSION_ROLE, nova_tenant, "restricted", "Restricted"),
        )
        connection.execute(
            "INSERT INTO role_assignments (id, tenant_id, membership_id, role_id) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (
                uuid5(TEST_NAMESPACE, "nova:no-permission:assignment"),
                nova_tenant,
                NO_PERMISSION_MEMBERSHIP,
                NO_PERMISSION_ROLE,
            ),
        )
    yield


@pytest.fixture
def admin_connection(postgres_seed: None) -> Iterator[Connection[tuple[object, ...]]]:
    with psycopg.connect(admin_dsn()) as connection:
        yield connection


@pytest.fixture
def runtime_connection(postgres_seed: None) -> Iterator[Connection[tuple[object, ...]]]:
    with psycopg.connect(runtime_dsn()) as connection:
        yield connection


@pytest_asyncio.fixture
async def runtime_engine(postgres_seed: None) -> AsyncIterator[AsyncEngine]:
    dsn = runtime_dsn().replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(Settings(environment="test", database_dsn=SecretStr(dsn)))
    yield engine
    await engine.dispose()
