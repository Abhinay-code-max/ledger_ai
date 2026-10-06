# LedgerAI backend and shared contracts

Phase 1 adds a secure FastAPI and PostgreSQL foundation around the independently importable Phase
0 contract package. It implements external JWT verification, membership-derived tenant context,
scoped RBAC, PostgreSQL row-level security, deterministic NOVA data, and foundational workspace
reads. It does not implement document ingestion, jobs, events, object storage, or agent workflows.

Canonical Pydantic models live in `src/ledgerai_contracts/v1`, generated JSON Schemas
in `shared/schemas/v1`, and synthetic examples in `shared/fixtures/contracts/v1`.

```shell
uv sync --all-extras --frozen
docker compose up -d postgres
uv run alembic upgrade head
uv run ledgerai-seed
uv run uvicorn ledgerai_backend.main:app
```

Every external top-level payload must include `schema_version`; v1 never assumes a missing version.
`uv.lock` is authoritative. Update dependencies with `uv lock --upgrade-package <name>`, review the
diff, then run `uv sync --all-extras --frozen`. Python 3.11 is the minimum; the lock includes newer
supported interpreters. Never commit `.env`; copy `.env.example` and replace only local values.

See `docs/integration/cross-role-contracts-v1.md` for team usage and
`docs/backend/phase1.md` for architecture, setup, configuration, migrations, RLS, permissions,
testing, recovery, and independent review instructions.
