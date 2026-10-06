# ADR 0014: uv is the reproducible Python dependency workflow

- Status: Accepted and implemented in Phase 1.
- Context: Phase 0 intentionally deferred a lock decision, but Phase 1 adds runtime and database
  dependencies.
- Decision: `pyproject.toml` declares supported ranges and `uv.lock` freezes complete resolution.
  CI and clean installs use `uv sync --all-extras --frozen`; Python 3.11 remains the minimum.
- Dependency rationale: FastAPI/Uvicorn serve HTTP; SQLAlchemy and psycopg provide typed async
  PostgreSQL access; Alembic owns migrations; Pydantic Settings validates configuration; PyJWT and
  cryptography verify external tokens; OpenTelemetry API preserves vendor-neutral observability;
  HTTPX, pytest-asyncio, jsonschema, mypy, Ruff, and pytest are test/development tools.
- Exclusions: Redis, Celery, S3, OCR, CSV ingestion, and AI frameworks belong to later phases.
