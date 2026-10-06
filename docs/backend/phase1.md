# Phase 1 backend foundation

## Architecture and trust boundaries

The FastAPI application factory is `ledgerai_backend.main:create_app`. Phase 0 contracts remain
independently importable and initialize no infrastructure. A request passes through trusted-host,
CORS, size/timeout, and request-ID controls before external token verification. Verified
issuer/subject and a requested workspace code enter the narrow membership-bootstrap function.
The returned active membership—not request JSON—defines tenant scope. Permission checks occur
before a tenant-explicit repository query, and PostgreSQL RLS independently applies the same
tenant ID.

Identity uses asymmetric JWT verification through `IdentityProviderPort`. Production requires
issuer, audience, an algorithm allowlist, and either a public key or JWKS URL. Signature,
expiration, not-before, issuer, audience, subject, required claims, algorithm, and JWKS key ID are
validated. JWKS retrieval has a two-second timeout and five-minute cache. The deterministic test
adapter is dependency-injected and production configuration rejects its activation.

Logs are JSON and recursively redact authorization, tokens, credentials, claims, secrets, and
DSNs. External failures use the Phase 0 `ErrorEnvelope`; unexpected errors receive only an opaque
internal diagnostic UUID. Raw SQL, DSNs, stack traces, token contents, and financial payloads are
never returned.

## Installation and dependencies

```shell
uv sync --all-extras --frozen
```

`uv.lock` is committed. To update one package, run `uv lock --upgrade-package PACKAGE`, inspect
both dependency files, then repeat complete verification. Python 3.11 is the supported minimum.
Runtime dependencies are limited to FastAPI/Uvicorn, SQLAlchemy/Alembic/psycopg, Pydantic
Settings, PyJWT/cryptography, and the OpenTelemetry API. HTTPX and quality/test tools are
development-only.

## Configuration reference

All variables use the `LEDGERAI_` prefix. `.env.example` contains safe local placeholders.

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `development`, `test`, or fail-closed `production` |
| `API_HOST`, `API_PORT` | Bind address and port |
| `DATABASE_DSN` | Secret async runtime-role PostgreSQL DSN |
| `MIGRATION_DSN` | Secret migration-owner PostgreSQL DSN |
| `ALLOWED_HOSTS` | JSON host allowlist |
| `CORS_ORIGINS` | JSON origin allowlist; empty by default |
| `JWT_ISSUER`, `JWT_AUDIENCE` | Required production claims |
| `JWT_ALGORITHMS` | Explicit allowlist; `none` is forbidden |
| `JWKS_URL`, `JWT_PUBLIC_KEY` | Rotating JWKS or configured asymmetric key |
| `ENABLE_TEST_IDENTITY` | Explicit test-only switch, rejected in production |
| `LOG_LEVEL`, `SERVICE_NAME`, `SERVICE_VERSION` | Safe telemetry metadata |
| `REQUEST_TIMEOUT_SECONDS`, `MAX_REQUEST_BYTES` | Request guardrails |

Secrets are `SecretStr` values and remain redacted from configuration representations.

## Database model and roles

`ledgerai_migrator` owns schema changes. `ledgerai_runtime` is a separate login, owns no protected
table, is non-superuser, has no role creation/database creation, uses `NOINHERIT`, and lacks
`BYPASSRLS`.

Tables are `tenants`, `organizations`, `legal_entities`, `principals`, `memberships`, `roles`,
`permissions`, `role_permissions`, and `role_assignments`. Composite foreign keys carry tenant and
parent scope. Normalized codes are unique inside their parent. Explicit status enums, non-empty
checks, scope hierarchy checks, issuer/subject uniqueness, active-membership uniqueness, UTC
timestamps, and optimistic versions are database-enforced. No financial column exists in Phase 1.

Every tenant-bearing table has `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and one
read/write policy with both `USING` and `WITH CHECK`. `ledgerai.current_tenant_id()` reads
`app.tenant_id`; absent context returns no rows and rejects writes. The app uses bound parameters
with transaction-local `set_config(..., true)`, so commit/rollback clears pooled connections.

The bootstrap function is documented in ADR 0013. The runtime role has no direct principal-table
grant. Tests prove invalid subject, revoked membership, foreign selectors, missing context,
cross-tenant reads/writes, concurrent tenants, and pool reuse cannot cross the boundary.

## Migrations, local PostgreSQL, and recovery

```shell
docker compose up -d postgres
uv run alembic upgrade head
uv run alembic current
uv run alembic heads
```

There must be exactly one head: `20261006_01`. DDL is transactional. If an upgrade fails, preserve
the error, do not stamp past it, restore a backup when any nontransactional operation was involved,
correct the migration, and retry on a copy first. For disposable local data only, stop the stack
and remove its named volume, then recreate and migrate. Never reset a shared or production
database.

## Permission matrix

| Role | Core Phase 1 permissions |
|---|---|
| Tenant administrator | All defined permissions |
| Entity administrator | Workspace/membership administration and all entity operations |
| Accountant | Workspace read, document placeholders, statements, close request |
| Reviewer | Workspace/document read and review action |
| Operator | Workspace read and document placeholders |
| Viewer | Workspace/document/statement read |

Document, review, close, statement, and audit codes reserve authorization vocabulary only; Phase 1
exposes no corresponding business endpoints.

## API surface

Public utility endpoints are `GET /health/live`, `GET /health/ready`, and `GET /version`.
Authenticated endpoints are:

- `GET /api/v1/me`
- `GET /api/v1/organizations`
- `GET /api/v1/organizations/{organization_id}`
- `GET /api/v1/legal-entities`
- `GET /api/v1/legal-entities/{legal_entity_id}`

Send a bearer token and `X-Workspace-Code`. Optional `X-Organization-ID` and
`X-Legal-Entity-ID` selectors are accepted only when covered by verified membership. Lists use
bounded `limit` (maximum 100) and `offset`. Foreign IDs return the same neutral not-found response.
Request and correlation headers contain UUIDs; invalid values are replaced and response headers
always carry the effective values. The canonical OpenAPI document is `shared/openapi/v1.json`.

Example (use an externally issued token; the seed does not create one):

```shell
curl -H "Authorization: Bearer $TOKEN" \
  -H "X-Workspace-Code: nova" \
  -H "X-Correlation-ID: 1d96ca19-2dfd-44cf-9107-87070382093d" \
  http://127.0.0.1:8000/api/v1/organizations?limit=50
```

## Synthetic NOVA seed

```shell
uv run ledgerai-seed
```

The idempotent seed creates the NOVA tenant, one organization, one Indian legal entity, six roles,
and synthetic subjects `nova-admin`, `nova-accountant`, and `nova-viewer` under issuer
`https://identity.demo.invalid/`. UUIDv5 mappings are stable. It stores no password, email, token,
or real person. Production execution requires the explicit `--allow-production` safeguard.

## Verification

Set `LEDGERAI_TEST_ADMIN_DSN` and `LEDGERAI_TEST_RUNTIME_DSN` to local synthetic roles, then:

```shell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests tools
uv run python tools/generate_contract_artifacts.py --check
uv run python tools/generate_openapi.py --check
uv run pytest
uv run python -m compileall -q src tools tests
```

For independent security review, prioritize direct runtime-role queries without context, wrong
tenant `WITH CHECK` writes, pool reuse after commit/rollback, concurrent tenants, revoked
membership, issuer/subject ambiguity, foreign scope headers and object IDs, forged JWT algorithms,
wrong claims/signatures, and searches of logs/errors for token or DSN material.

## Known limitations and Phase 2 boundary

Phase 1 has no document upload, object storage, OCR, CSV ingestion, job/event processing, agent
orchestration, approval workflow, audit endpoint, period close, or financial statement endpoint.
Remote JWKS depends on provider availability; production should add provider-specific resilience
and revocation policy. Offset pagination is bounded but can move under concurrent administration;
a future version may adopt opaque cursors. OpenTelemetry exporters and deployment secret
management remain platform integration work.
