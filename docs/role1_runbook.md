# LedgerAI Role 1: Document Intelligence Runbook

## Overview
Role 1 is the Document Intelligence service for LedgerAI. It ingests immutable document references from Role 4, executes layout-aware OCR and pretrained vision-language extraction baselines, validates financial invariants (arithmetic, dates, currencies), and produces schema-valid `DocumentExtraction` contracts with field-level provenance and confidence.

## Service Endpoints
- `POST /v1/extractions`: Primary typed extraction endpoint. Expects Role 4 service JWT authentication.
- `GET /health/live`: Liveness probe. Returns HTTP 200 `{"status": "live"}`.
- `GET /health/ready`: Readiness probe. Returns HTTP 200 `{"status": "ready"}`.
- `GET /metrics`: Service telemetry and extraction stats (authenticated).

## Local Development & Setup

### 1. Prerequisites
- Python 3.11+
- `uv` package manager

### 2. Running Tests
Run all Role 1 test suites (governance, ontology, evaluation, security, and Role 4 adapter compatibility):
```powershell
uv run pytest tests/role1 -v
```

Run linting and formatting verification:
```powershell
uv run ruff check src/ledgerai_role1 tests/role1
uv run ruff format --check src/ledgerai_role1 tests/role1
```

Run strict static typing checks:
```powershell
uv run mypy -p ledgerai_role1
```

### 3. Running the Service Locally
Launch the Role 1 FastAPI application on port 8101:
```powershell
uv run uvicorn ledgerai_role1.service.app:app --host 0.0.0.0 --port 8101
```

### 4. Running the Evaluation Harness
Execute deterministic evaluation against the held-out frozen test dataset and generate the error analysis report:
```powershell
uv run python src/ledgerai_role1/evaluation/run_eval.py
```
This updates `docs/error_analysis_report.md` with measured exact match, CER, calibration error, and acceptance criteria decisions.

### 5. Docker Container Build & Run
Build the minimal, unprivileged container:
```bash
docker build -f Dockerfile.role1 -t ledgerai-role1:latest .
```

Run in an isolated network sandbox:
```bash
docker run --rm -p 8101:8101 \
  -e LEDGERAI_ROLE1_SERVICE_TOKEN_SECRET="replace-with-at-least-32-random-bytes" \
  ledgerai-role1:latest
```

## Security & Operational Controls
- **Adversarial Input Quarantining**: Document text containing prompt-injection attempts is flagged and quarantined; the resulting extraction is forced into `REVIEW_REQUIRED` disposition.
- **Zero Logging of Sensitive Content**: Extracted invoice text and PII are never logged in application traces.
- **Strict Decimal Arithmetic**: Floating-point parsing is disabled. All amounts must balance (`subtotal + tax == total`), or an `ARITHMETIC_TOTAL_MISMATCH` issue is recorded.
- **Idempotency**: Requests carrying the same `operation_id` within a tenant return the identical cached `DocumentExtraction` record without re-processing.
