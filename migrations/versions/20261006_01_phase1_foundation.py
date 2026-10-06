"""Create the Phase 1 tenancy, RBAC, and RLS foundation."""

from collections.abc import Sequence

from alembic import op

from ledgerai_backend.database.base import Base
from ledgerai_backend.tenancy import models  # noqa: F401

revision: str = "20261006_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "tenants",
    "organizations",
    "legal_entities",
    "memberships",
    "roles",
    "role_permissions",
    "role_assignments",
)


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.execute("CREATE SCHEMA IF NOT EXISTS ledgerai")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ledgerai.current_tenant_id()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        SET search_path = pg_catalog
        AS $$
          SELECT nullif(current_setting('app.tenant_id', true), '')::uuid
        $$
        """
    )
    for table in TENANT_TABLES:
        tenant_column = "id" if table == "tenants" else "tenant_id"
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON public.{table}
            USING ({tenant_column} = ledgerai.current_tenant_id())
            WITH CHECK ({tenant_column} = ledgerai.current_tenant_id())
            """
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION ledgerai.bootstrap_authorization(
          p_issuer text,
          p_subject text,
          p_workspace_code text,
          p_organization_id uuid DEFAULT NULL,
          p_legal_entity_id uuid DEFAULT NULL
        )
        RETURNS TABLE(
          principal_id uuid,
          membership_id uuid,
          tenant_id uuid,
          organization_id uuid,
          legal_entity_id uuid,
          roles text[],
          permissions text[]
        )
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          WITH eligible AS (
            SELECT p.id AS principal_id,
                   m.id AS membership_id,
                   t.id AS tenant_id,
                   COALESCE(p_organization_id, m.organization_id) AS organization_id,
                   COALESCE(p_legal_entity_id, m.legal_entity_id) AS legal_entity_id
            FROM public.principals p
            JOIN public.memberships m ON m.principal_id = p.id
            JOIN public.tenants t ON t.id = m.tenant_id
            WHERE p.issuer = p_issuer
              AND p.external_subject = p_subject
              AND p.status = 'ACTIVE'
              AND t.code = lower(p_workspace_code)
              AND t.status = 'ACTIVE'
              AND m.status = 'ACTIVE'
              AND (m.valid_from IS NULL OR m.valid_from <= statement_timestamp())
              AND (m.valid_until IS NULL OR m.valid_until > statement_timestamp())
              AND (p_legal_entity_id IS NULL OR p_organization_id IS NOT NULL)
              AND (
                p_organization_id IS NULL OR EXISTS (
                  SELECT 1 FROM public.organizations o
                  WHERE o.tenant_id = t.id AND o.id = p_organization_id AND o.status = 'ACTIVE'
                )
              )
              AND (
                p_legal_entity_id IS NULL OR EXISTS (
                  SELECT 1 FROM public.legal_entities le
                  WHERE le.tenant_id = t.id
                    AND le.organization_id = p_organization_id
                    AND le.id = p_legal_entity_id
                    AND le.status = 'ACTIVE'
                )
              )
              AND (m.organization_id IS NULL OR m.organization_id = p_organization_id)
              AND (m.legal_entity_id IS NULL OR m.legal_entity_id = p_legal_entity_id)
            ORDER BY (m.legal_entity_id IS NOT NULL) DESC,
                     (m.organization_id IS NOT NULL) DESC,
                     m.created_at,
                     m.id
            LIMIT 1
          )
          SELECT e.principal_id,
                 e.membership_id,
                 e.tenant_id,
                 e.organization_id,
                 e.legal_entity_id,
                 COALESCE(array_agg(DISTINCT r.code) FILTER (WHERE r.code IS NOT NULL), ARRAY[]::text[]),
                 COALESCE(array_agg(DISTINCT rp.permission_code) FILTER (WHERE rp.permission_code IS NOT NULL), ARRAY[]::text[])
          FROM eligible e
          LEFT JOIN public.role_assignments ra
            ON ra.tenant_id = e.tenant_id
           AND ra.membership_id = e.membership_id
           AND (ra.organization_id IS NULL OR ra.organization_id = e.organization_id)
           AND (ra.legal_entity_id IS NULL OR ra.legal_entity_id = e.legal_entity_id)
          LEFT JOIN public.roles r
            ON r.tenant_id = ra.tenant_id AND r.id = ra.role_id
          LEFT JOIN public.role_permissions rp
            ON rp.tenant_id = r.tenant_id AND rp.role_id = r.id
          GROUP BY e.principal_id, e.membership_id, e.tenant_id,
                   e.organization_id, e.legal_entity_id
        $$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION ledgerai.bootstrap_authorization(text, text, text, uuid, uuid) FROM PUBLIC"
    )
    op.execute("REVOKE ALL ON FUNCTION ledgerai.current_tenant_id() FROM PUBLIC")
    op.execute("GRANT USAGE ON SCHEMA ledgerai TO ledgerai_runtime")
    op.execute(
        "GRANT EXECUTE ON FUNCTION ledgerai.bootstrap_authorization(text, text, text, uuid, uuid) TO ledgerai_runtime"
    )
    op.execute("GRANT EXECUTE ON FUNCTION ledgerai.current_tenant_id() TO ledgerai_runtime")
    for table in TENANT_TABLES:
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{table} TO ledgerai_runtime"
        )
    op.execute("ALTER ROLE ledgerai_runtime SET row_security = on")


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS ledgerai.bootstrap_authorization(text, text, text, uuid, uuid)"
    )
    Base.metadata.drop_all(bind=op.get_bind())
    op.execute("DROP FUNCTION IF EXISTS ledgerai.current_tenant_id()")
    op.execute("DROP SCHEMA IF EXISTS ledgerai")
