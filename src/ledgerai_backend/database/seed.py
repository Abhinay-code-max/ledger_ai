"""Idempotent, production-guarded synthetic NOVA workspace seed."""

from __future__ import annotations

import argparse
from uuid import UUID, uuid5

from sqlalchemy import create_engine, text

from ledgerai_backend.core.config import Settings

SEED_NAMESPACE = UUID("15c191c2-81d1-4f79-8a38-7d8543649c71")


def stable_id(name: str) -> UUID:
    return uuid5(SEED_NAMESPACE, name)


PERMISSIONS = {
    "workspace:read": "Read workspace hierarchy",
    "workspace:admin": "Administer workspace settings",
    "membership:admin": "Administer memberships",
    "document:read": "Read documents, imports, and safe ingestion results",
    "document:write": "Upload documents, import transactions, and retry ingestion jobs",
    "review:act": "Act on review items",
    "reconciliation:read": "Read reconciliation proposals",
    "exception:read": "Read workflow exceptions",
    "review:read": "Read approval requests",
    "review:approve": "Approve eligible proposal versions",
    "review:correct": "Create corrected proposal versions",
    "review:reject": "Reject proposal versions",
    "review:request_evidence": "Request additional proposal evidence",
    "review:escalate": "Escalate proposal review",
    "policy:read": "Read policy sets and historical decisions",
    "policy:admin": "Administer unpublished policy versions",
    "financial-statement:read": "Read financial statements",
    "period-close:request": "Request period close",
    "posting:execute": "Execute an approved journal posting",
    "progress:read": "Read and stream workflow progress",
    "audit:read": "Read audit records",
}

ROLE_PERMISSIONS = {
    "tenant-administrator": set(PERMISSIONS),
    "entity-administrator": {
        "workspace:read",
        "workspace:admin",
        "membership:admin",
        "document:read",
        "document:write",
        "review:act",
        "financial-statement:read",
        "period-close:request",
        "posting:execute",
        "progress:read",
        "audit:read",
    },
    "accountant": {
        "workspace:read",
        "document:read",
        "document:write",
        "financial-statement:read",
        "period-close:request",
        "reconciliation:read",
        "exception:read",
        "review:read",
        "review:correct",
        "review:request_evidence",
        "policy:read",
        "progress:read",
    },
    "reviewer": {
        "workspace:read",
        "document:read",
        "review:act",
        "reconciliation:read",
        "exception:read",
        "review:read",
        "review:approve",
        "review:reject",
        "review:request_evidence",
        "review:escalate",
        "policy:read",
        "progress:read",
    },
    "operator": {
        "workspace:read",
        "document:read",
        "document:write",
        "reconciliation:read",
        "exception:read",
        "review:read",
        "progress:read",
    },
    "viewer": {
        "workspace:read",
        "document:read",
        "financial-statement:read",
        "reconciliation:read",
        "exception:read",
        "review:read",
        "policy:read",
    },
}


def seed(settings: Settings, *, allow_production: bool = False) -> dict[str, int]:
    if settings.environment == "production" and not allow_production:
        raise RuntimeError("production seeding requires --allow-production")
    if not settings.migration_dsn:
        raise RuntimeError("LEDGERAI_MIGRATION_DSN is required for seeding")
    tenant_id = stable_id("nova:tenant")
    organization_id = stable_id("nova:organization")
    legal_entity_id = stable_id("nova:legal-entity")
    principals = {
        "nova-admin": "NOVA Demo Administrator",
        "nova-accountant": "NOVA Demo Accountant",
        "nova-viewer": "NOVA Demo Viewer",
    }
    engine = create_engine(settings.migration_dsn.get_secret_value())
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tenants (id, name, code, status) VALUES (:id, :name, :code, 'ACTIVE') ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tenant_id, "name": "NOVA TECHNOLOGIES PVT LTD", "code": "nova"},
        )
        connection.execute(
            text(
                "INSERT INTO organizations (id, tenant_id, name, code, status) VALUES (:id, :tenant, :name, :code, 'ACTIVE') ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": organization_id,
                "tenant": tenant_id,
                "name": "NOVA Technologies",
                "code": "nova-india",
            },
        )
        connection.execute(
            text("""
                INSERT INTO legal_entities
                  (id, tenant_id, organization_id, legal_name, display_name, code, country_code, status)
                VALUES (:id, :tenant, :organization, :legal_name, :display_name, :code, :country, 'ACTIVE')
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": legal_entity_id,
                "tenant": tenant_id,
                "organization": organization_id,
                "legal_name": "NOVA TECHNOLOGIES PVT LTD",
                "display_name": "NOVA Technologies India",
                "code": "nova-technologies-in",
                "country": "IN",
            },
        )
        for code, description in PERMISSIONS.items():
            connection.execute(
                text(
                    "INSERT INTO permissions (code, description) VALUES (:code, :description) "
                    "ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description"
                ),
                {"code": code, "description": description},
            )
        for role_code, permissions in ROLE_PERMISSIONS.items():
            role_id = stable_id(f"nova:role:{role_code}")
            connection.execute(
                text(
                    "INSERT INTO roles (id, tenant_id, code, name) VALUES (:id, :tenant, :code, :name) ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "id": role_id,
                    "tenant": tenant_id,
                    "code": role_code,
                    "name": role_code.replace("-", " ").title(),
                },
            )
            for permission in permissions:
                connection.execute(
                    text(
                        "INSERT INTO role_permissions (tenant_id, role_id, permission_code) VALUES (:tenant, :role, :permission) ON CONFLICT DO NOTHING"
                    ),
                    {"tenant": tenant_id, "role": role_id, "permission": permission},
                )
        for subject, display_name in principals.items():
            principal_id = stable_id(f"principal:{subject}")
            membership_id = stable_id(f"nova:membership:{subject}")
            connection.execute(
                text(
                    "INSERT INTO principals (id, issuer, external_subject, display_name, status) VALUES (:id, :issuer, :subject, :display_name, 'ACTIVE') ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "id": principal_id,
                    "issuer": "https://identity.demo.invalid/",
                    "subject": subject,
                    "display_name": display_name,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO memberships (id, tenant_id, principal_id, status) VALUES (:id, :tenant, :principal, 'ACTIVE') ON CONFLICT (id) DO NOTHING"
                ),
                {"id": membership_id, "tenant": tenant_id, "principal": principal_id},
            )
            role_code = {
                "nova-admin": "tenant-administrator",
                "nova-accountant": "accountant",
                "nova-viewer": "viewer",
            }[subject]
            connection.execute(
                text(
                    "INSERT INTO role_assignments (id, tenant_id, membership_id, role_id) VALUES (:id, :tenant, :membership, :role) ON CONFLICT (id) DO NOTHING"
                ),
                {
                    "id": stable_id(f"nova:assignment:{subject}:{role_code}"),
                    "tenant": tenant_id,
                    "membership": membership_id,
                    "role": stable_id(f"nova:role:{role_code}"),
                },
            )
    engine.dispose()
    return {
        "tenants": 1,
        "organizations": 1,
        "legal_entities": 1,
        "principals": len(principals),
        "roles": len(ROLE_PERMISSIONS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-production", action="store_true")
    args = parser.parse_args()
    summary = seed(Settings(), allow_production=args.allow_production)
    print(
        "NOVA synthetic workspace ready: "
        + ", ".join(f"{key}={value}" for key, value in summary.items())
    )


if __name__ == "__main__":
    main()
