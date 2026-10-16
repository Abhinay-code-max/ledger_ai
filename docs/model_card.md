# Model Card: LedgerAI Role 1 Document Intelligence Baseline (Corrected)

## Model Details
- **Model Name**: `docintel-foundation-vlm`
- **Claimed Model Architecture**: Vision-Language Foundation Baseline
- **Actual Runtime Implementation**: Deterministic Regex Layout Parser (`DeterministicBaselineExtractor`)
- **Reported Revision**: `sha256:d8a9f0e123456789abcdef0123456789abcdef0123456789abcdef0123456789`
- **Revision Verification Status**: **INVALID** (Placeholder repeating hexadecimal pattern `...abcdef0123456789...`)
- **Manifest Revision**: `18dce7558f6bd7136d53d0517d32542ae025f50b` (References 0-byte empty artifact hash `e3b0c442...`)
- **Actual Model Weights on Disk**: None (`models/model.onnx` missing from filesystem)
- **Real Weights Loaded in Role 6**: `False`
- **Real Model Baseline Status**: `NOT_EVALUATED`
- **Ontology & Algorithm Version**: `1.0.0`
- **Preprocessing Version**: `layout-sanitize-v1`
- **Prompt Template Version**: `nova-v1`
- **Producer Name**: `ledgerai-role1-docintel` (Type: `MODEL`)

## Intended Use
- **Primary Use**: Demonstration of deterministic evidence extraction for NOVA pipeline and Role 4 orchestration fixtures.
- **Supported Fixtures**: Synthetic Supplier Invoices, Customer Invoices, Receipts, Bank Statements, Purchase Orders.
- **Out-of-Scope**: Production automated extraction without verified neural model weights and diverse validation; unseen template generalization.

## Adversarial Robustness & Hostile Data Governance
- **Hostile Data Isolation**: Document text is strictly enclosed in boundary containers and treated as untrusted data, never as prompt instructions.
- **Prompt Injection Defense**: Multi-pattern scanner detects and quarantines jailbreak and instruction-override attempts inside invoices and OCR text.
- **Prohibited Tool Invocations**: Model output cannot trigger tools or bypass Role 4 policies.
- **No In-Flight Content Logging**: Document content, names, and financial line values are never written to server access logs.
- **Floating-Point Ban**: Financial amounts strictly parsed and serialized as `Decimal` strings.

## Corrected Evaluation Results: `NOVA_SYNTHETIC_FIXTURE_RESULT`
Measured on held-out test split of `NOVA-Financial-Documents-Synthetic` (5 documents, 1 document per supported document type) executed through the actual Role 6 FastAPI Model Gateway (`/v1/models/infer`) with signed service token authentication and tenant context:

> [!WARNING]
> **Accuracy Claim Correction**: Five synthetic documents (N=1 per document type) evaluated through a deterministic CPU backend establish **only** deterministic demo fixture readiness. They do **not** establish production accuracy, general document intelligence accuracy, or real VLM accuracy. Model training cannot be claimed unnecessary for unseen documents.

| Metric | Sample Size | Measured Value | Pre-declared Target | Fixture Status |
|---|---|---|---|---|
| **Invalid Schema Rate** | N=5 | `0.00%` | `<= 0.00%` | PASSED (Fixture) |
| **Decimal Amount Exact Match** | N=5 | `100.00%` | `>= 95.00%` | PASSED (Fixture) |
| **Date Accuracy** | N=5 | `100.00%` | `>= 95.00%` | PASSED (Fixture) |
| **Currency Accuracy** | N=5 | `100.00%` | `>= 98.00%` | PASSED (Fixture) |
| **Line-Item Extraction Accuracy** | N=5 | `100.00%` | `>= 90.00%` | PASSED (Fixture) |
| **Field-level F1 (Mean)** | N=5 | `1.00` | `>= 0.95` | PASSED (Fixture) |
| **Hallucination Rate** | N=5 | `0.00%` | `<= 2.00%` | PASSED (Fixture) |
| **Character Error Rate (CER)** | N=5 | `0.0000` | `<= 0.05` | PASSED (Fixture) |
| **Confidence Calibration Error** | N=5 | `0.0281` | - | Evaluated |
| **Mean Latency per Doc** | N=5 | `0.0588s` | `<= 1.00s` | PASSED (Fixture) |
| **Timeout / Error Rate** | N=5 | `0.00%` | `<= 0.00%` | PASSED (Fixture) |
| **Peak Memory Usage** | N=5 | `1.41 MB` | - | Evaluated |

### Hostile Document Robustness (Through Role 6 Gateway)
- **Prompt Injections Tested**: Quarantined (100.0% defense rate, zero command execution)
- **Hidden Instructions**: Detected & quarantined via spatial layout scanner
- **Misleading Totals**: Caught via `ARITHMETIC_TOTAL_MISMATCH`
- **Malformed Dates & Currencies**: Safely handled with zero crashes, unparseable dates set to `None`
- **Conflicting Line-Item Totals**: Caught via `LINE_ITEM_TOTAL_MISMATCH`
- **Hostile Metadata & Traversal**: Rejected with HTTP 400 / 422
- **Unsupported Language/Layout**: Safely abstained as `UNKNOWN` document type (100% abstention rate)

## Training Decisions & Blockers

### Demo Training Decision: `DEMO_TRAINING_NOT_REQUIRED`
The deterministic NOVA demo functions as intended on all five synthetic document fixtures.

### Production Training Decision: `TRAINING_REQUIRED_BUT_BLOCKED`
- **Blockers**:
  1. `NO_VERIFIED_BASE_MODEL_ARTIFACT`: Base model `docintel-foundation-vlm` has no verified weights, provider source, or non-empty SHA-256 artifact.
  2. `NO_REAL_MODEL_WEIGHTS_LOADED`: Role 6 operates via `DeterministicInferenceBackend`.
  3. `INSUFFICIENT_EVALUATION_DIVERSITY_N5`: Real baseline requires multiple independent templates per document type with confidence intervals.
  4. `DETERMINISTIC_FIXTURE_BACKEND_ONLY`: Real VLM baseline cannot be evaluated on deterministic regex backend.
