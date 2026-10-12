# LedgerAI Role 6 Local Model Runtime & Infrastructure Guide

## Overview

Role 6 provides a secure, bounded, provider-neutral model serving runtime and local inference gateway designed for consumption by Role 1 Document Intelligence and orchestration by Role 4.

Role 6 owns:
- Model serving and runtime isolation
- Hard resource bounds enforcement (request bytes, pages, pixels, tokens, concurrency, queue depth)
- Cryptographically validated model manifests
- Provider-neutral runtime backends (Deterministic Baseline, Real ONNX / Local runtime adapter)
- Operational health, readiness, and observability
- Reproducible benchmark harness

Role 6 **does not own** accounting, financial posting, approvals, period close, or document semantics.

---

## Architecture & Security Boundaries

1. **Authentication & Authorization**:
   - Every inference request requires a short-lived HMAC-SHA256 signed service token.
   - Required claims: `iss`, `sub`, `aud`, `exp`, `iat`, `tenant_id`, `operation_id`.
   - Audience: `ledgerai-role6`.
   - The gateway strictly validates that caller headers and token claims match tenant and operation context.

2. **Hostile Input Treatment**:
   - Document text is treated strictly as untrusted data, never instructions.
   - Arbitrary model selection, arbitrary filesystem paths, and external URLs are forbidden.
   - Outbound network access is disabled by default.
   - Storage references must conform to the allowlisted prefix (default: `ledgerai-evidence/`) and forbid path traversal.

3. **Telemetry & Redaction**:
   - Telemetry logs operation IDs, correlation IDs, tenant IDs, model revisions, latencies, and outcomes.
   - Prompt texts, document tokens, extracted financial fields, and authorization headers are never logged.

---

## Model Manifests

Model manifests are strictly validated against `ModelManifest` (`shared/schemas/v1/model-runtime.schema.json`):
- Location: `models/manifests/ledgerai_docintel_v1.manifest.json`
- Fields:
  - `model_id`: Canonical model identifier (e.g., `docintel-foundation-vlm`)
  - `model_name`: Model name
  - `backend_type`: `DETERMINISTIC`, `ONNX`, `VLLM`, etc.
  - `immutable_revision`: Git SHA / artifact revision
  - `artifact_hashes`: Map of artifact relative paths to SHA-256 hashes
  - `preprocessing_version`: Version token
  - `supported_capabilities`: Explicit array (`DOCUMENT_EXTRACTION`, `DOCUMENT_CLASSIFICATION`, etc.)
  - `supported_input_types`: Explicit media types (`text/plain`, `application/pdf`, etc.)
  - `limits`: Max request bytes, max pages, max image pixels, max tokens, timeouts, concurrency limits.

---

## Operating Modes

### 1. Deterministic Test Baseline (Default)
Used for automated testing, CI, and verifiable reproducible benchmarks.
- Environment variables:
  ```env
  LEDGERAI_ROLE6_ACTIVE_BACKEND=deterministic
  LEDGERAI_ROLE6_SERVICE_AUDIENCE=ledgerai-role6
  LEDGERAI_ROLE6_SERVICE_TOKEN_SECRET=local-service-token-secret-32-chars-minimum
  ```
- Startup:
  ```bash
  uv run uvicorn ledgerai_role6.app:create_role6_app --factory --host 127.0.0.1 --port 8006
  ```

### 2. Configuration-Driven Real Backend
Enables execution with real weights and runtime device selection:
- Environment variables:
  ```env
  LEDGERAI_ROLE6_ACTIVE_BACKEND=real_onnx
  LEDGERAI_ROLE6_MODEL_MANIFEST_PATH=models/manifests/ledgerai_docintel_v1.manifest.json
  LEDGERAI_ROLE6_MODEL_ARTIFACTS_DIR=models/artifacts
  ```

---

## Benchmark Harness

Run reproducible latency and throughput benchmarks producing machine-readable JSON:
```bash
uv run python -m ledgerai_role6.benchmark --requests 50 --warmup 5 --concurrency 2
```

Outputs include:
- `backend_type` and clear `Deterministic Test Baseline` identification
- Model and preprocessing immutable revisions
- System OS, processor, and runtime details
- Measured p50, p95, and p99 latencies in ms
- Measured throughput (req/s)
