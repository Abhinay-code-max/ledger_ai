# LedgerAI shared contracts

Phase 0 establishes LedgerAI's versioned cross-role contract foundation. It contains no
backend workflows, persistence, queues, authentication implementation, or external
integrations.

Canonical Pydantic models live in `src/ledgerai_contracts/v1`, generated JSON Schemas
in `shared/schemas/v1`, and synthetic examples in `shared/fixtures/contracts/v1`.

```powershell
python -m pip install -e ".[dev]"
python tools/generate_contract_artifacts.py --check
pytest
ruff check .
mypy src tests tools
```

Every external top-level payload must include `schema_version`; v1 never assumes a missing version.
The project had no established lock mechanism before publication and currently uses bounded
dependencies with setuptools/pip. The Phase 0 gate was tested with Python 3.14.4, Pydantic 2.13.4,
pytest 9.1.1, jsonschema 4.26.0, mypy 1.20.2, and Ruff 0.16.10. Selecting a final lock mechanism
remains a team decision; Phase 1 dependency additions must not proceed until it is resolved.

See `docs/integration/cross-role-contracts-v1.md` for team usage and
`docs/architecture/role4-repository-assessment.md` for the verified repository assessment.
