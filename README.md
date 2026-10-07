# LedgerAI backend and shared contracts

Phase 2 adds immutable quarantined document intake, private S3-compatible storage, bounded bank CSV
normalization, durable HTTP idempotency, processing-job state, a transactional outbox, consumer
inbox deduplication, and Celery/Redis dispatch behind infrastructure ports. Tenant context still
comes from Phase 1 identity and membership, and every new business table is protected by forced
PostgreSQL row-level security.

Canonical Pydantic models live in `src/ledgerai_contracts/v1`, generated JSON Schemas
in `shared/schemas/v1`, and synthetic examples in `shared/fixtures/contracts/v1`.

```shell
uv sync --all-extras --frozen
docker compose up -d postgres redis minio minio-init
uv run alembic upgrade head
uv run ledgerai-seed
uv run uvicorn ledgerai_backend.main:app
```

Every external top-level payload must include `schema_version`; v1 never assumes a missing version.
`uv.lock` is authoritative. Update dependencies with `uv lock --upgrade-package <name>`, review the
diff, then run `uv sync --all-extras --frozen`. Python 3.11 is the minimum; the lock includes newer
supported interpreters. Never commit `.env`; copy `.env.example` and replace only local values.

See `docs/integration/cross-role-contracts-v1.md` for team usage and
`docs/backend/phase1.md` and `docs/backend/phase2.md` for architecture, setup, configuration,
migrations, RLS, ingestion, reliability, recovery, and independent review instructions.
