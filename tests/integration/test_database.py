from __future__ import annotations

import asyncio
from typing import cast
from uuid import uuid4

import psycopg
import pytest
from phase1_postgres_support import ACME_ORGANIZATION, ACME_TENANT, runtime_dsn
from psycopg import Connection
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine

from ledgerai_backend.database.seed import stable_id

pytestmark = pytest.mark.postgres


def set_tenant(connection: Connection[tuple[object, ...]], tenant_id: object) -> None:
    connection.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))


def test_migration_head_schema_and_rls_are_present(
    admin_connection: Connection[tuple[object, ...]],
) -> None:
    revision = admin_connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert revision == ("20261008_04",)
    tables = admin_connection.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('tenants','organizations','legal_entities','principals','memberships','roles','permissions','role_permissions','role_assignments')"
    ).fetchone()
    assert tables == (9,)
    policies = admin_connection.execute(
        "SELECT count(*) FROM pg_policies WHERE schemaname='public'"
    ).fetchone()
    assert policies == (41,)


def test_runtime_role_is_non_owner_non_superuser_without_bypassrls(
    admin_connection: Connection[tuple[object, ...]],
) -> None:
    attributes = admin_connection.execute(
        "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname='ledgerai_runtime'"
    ).fetchone()
    assert attributes == (False, False)
    owner = admin_connection.execute(
        "SELECT tableowner FROM pg_tables WHERE schemaname='public' AND tablename='tenants'"
    ).fetchone()
    assert owner is not None and owner[0] != "ledgerai_runtime"


def test_missing_context_fails_closed(
    runtime_connection: Connection[tuple[object, ...]],
) -> None:
    assert runtime_connection.execute("SELECT count(*) FROM tenants").fetchone() == (0,)
    assert runtime_connection.execute("SELECT count(*) FROM organizations").fetchone() == (0,)


def test_rls_read_isolation(runtime_connection: Connection[tuple[object, ...]]) -> None:
    set_tenant(runtime_connection, stable_id("nova:tenant"))
    rows = runtime_connection.execute("SELECT code FROM tenants ORDER BY code").fetchall()
    assert rows == [("nova",)]
    assert runtime_connection.execute(
        "SELECT count(*) FROM organizations WHERE tenant_id=%s", (ACME_TENANT,)
    ).fetchone() == (0,)


def test_rls_rejects_foreign_insert(runtime_connection: Connection[tuple[object, ...]]) -> None:
    set_tenant(runtime_connection, stable_id("nova:tenant"))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        runtime_connection.execute(
            "INSERT INTO organizations (id, tenant_id, name, code, status) VALUES (%s, %s, %s, %s, 'ACTIVE')",
            (
                uuid4(),
                ACME_TENANT,
                "Foreign",
                "foreign",
            ),
        )


def test_rls_allows_scoped_insert_update_and_delete(
    runtime_connection: Connection[tuple[object, ...]],
) -> None:
    tenant_id = stable_id("nova:tenant")
    organization_id = uuid4()
    set_tenant(runtime_connection, tenant_id)
    runtime_connection.execute(
        "INSERT INTO organizations (id, tenant_id, name, code, status) VALUES (%s, %s, %s, %s, 'ACTIVE')",
        (organization_id, tenant_id, "Temporary Synthetic", f"temporary-{organization_id.hex}"),
    )
    updated = runtime_connection.execute(
        "UPDATE organizations SET name='Updated Synthetic' WHERE id=%s", (organization_id,)
    )
    deleted = runtime_connection.execute(
        "DELETE FROM organizations WHERE id=%s", (organization_id,)
    )
    assert updated.rowcount == 1
    assert deleted.rowcount == 1


def test_rls_foreign_update_and_delete_touch_nothing(
    runtime_connection: Connection[tuple[object, ...]],
) -> None:
    set_tenant(runtime_connection, stable_id("nova:tenant"))
    updated = runtime_connection.execute(
        "UPDATE organizations SET name='Hidden' WHERE id=%s", (ACME_ORGANIZATION,)
    )
    deleted = runtime_connection.execute(
        "DELETE FROM organizations WHERE id=%s", (ACME_ORGANIZATION,)
    )
    assert updated.rowcount == 0
    assert deleted.rowcount == 0


def test_bootstrap_is_narrow_and_principal_table_is_not_readable(
    runtime_connection: Connection[tuple[object, ...]],
) -> None:
    row = runtime_connection.execute(
        "SELECT tenant_id, permissions FROM ledgerai.bootstrap_authorization(%s, %s, %s, NULL, NULL)",
        ("https://identity.demo.invalid/", "nova-admin", "nova"),
    ).fetchone()
    assert row is not None
    assert row[0] == stable_id("nova:tenant")
    assert "workspace:read" in cast(list[str], row[1])
    assert (
        runtime_connection.execute(
            "SELECT * FROM ledgerai.bootstrap_authorization(%s, %s, %s, NULL, NULL)",
            ("https://identity.demo.invalid/", "unknown", "nova"),
        ).fetchone()
        is None
    )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        runtime_connection.execute("SELECT * FROM principals")


def test_pool_checkout_cannot_retain_transaction_local_tenant() -> None:
    engine = create_engine(runtime_dsn(), pool_size=1, max_overflow=0)
    with engine.begin() as connection:
        connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"),
            {"tenant": str(stable_id("nova:tenant"))},
        )
        assert connection.execute(text("SELECT count(*) FROM tenants")).scalar_one() == 1
    with engine.begin() as connection:
        assert (
            connection.execute(
                text("SELECT nullif(current_setting('app.tenant_id', true), '')")
            ).scalar_one()
            is None
        )
        assert connection.execute(text("SELECT count(*) FROM tenants")).scalar_one() == 0
    engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_tenant_contexts_are_isolated(runtime_engine: AsyncEngine) -> None:
    async def visible_code(tenant_id: object) -> str:
        async with runtime_engine.begin() as connection:
            await connection.execute(
                text("SELECT set_config('app.tenant_id', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            return str((await connection.execute(text("SELECT code FROM tenants"))).scalar_one())

    results = await asyncio.gather(
        visible_code(stable_id("nova:tenant")), visible_code(ACME_TENANT)
    )
    assert list(results) == ["nova", "acme"]


def test_database_constraints_reject_cross_tenant_and_duplicate_identity(
    admin_connection: Connection[tuple[object, ...]],
) -> None:
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        admin_connection.execute(
            """INSERT INTO legal_entities
               (id, tenant_id, organization_id, legal_name, display_name, code, country_code, status)
               VALUES (%s, %s, %s, 'Invalid', 'Invalid', 'invalid-cross-tenant', 'US', 'ACTIVE')""",
            (uuid4(), stable_id("nova:tenant"), ACME_ORGANIZATION),
        )
    admin_connection.rollback()
    with pytest.raises(psycopg.errors.UniqueViolation):
        admin_connection.execute(
            "INSERT INTO principals (id, issuer, external_subject, display_name, status) VALUES (%s, %s, %s, %s, 'ACTIVE')",
            (uuid4(), "https://identity.demo.invalid/", "nova-admin", "Duplicate"),
        )


def test_membership_scope_constraint_rejects_legal_entity_without_organization(
    admin_connection: Connection[tuple[object, ...]],
) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        admin_connection.execute(
            "INSERT INTO memberships (id, tenant_id, principal_id, legal_entity_id, status) VALUES (%s, %s, %s, %s, 'ACTIVE')",
            (uuid4(), ACME_TENANT, uuid4(), uuid4()),
        )


def test_duplicate_active_membership_at_same_scope_is_rejected(
    admin_connection: Connection[tuple[object, ...]],
) -> None:
    with pytest.raises(psycopg.errors.UniqueViolation):
        admin_connection.execute(
            "INSERT INTO memberships (id, tenant_id, principal_id, status) VALUES (%s, %s, %s, 'ACTIVE')",
            (uuid4(), stable_id("nova:tenant"), stable_id("principal:nova-admin")),
        )
