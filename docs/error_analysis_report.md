# Corrected Model Readiness Report: Role 1 Document Intelligence

## 1. Executive Summary & Result Classification
- **Result Classification**: `NOVA_SYNTHETIC_FIXTURE_RESULT` (Deterministic Fixture Verification)
- **Evaluation Mechanism**: Role 6 Model Runtime Gateway (`/v1/models/infer`)
- **Backend Type**: `DeterministicInferenceBackend` (CPU deterministic regex parsing)
- **Real Model Baseline Status**: `NOT_EVALUATED`
- **Training Decision**: `TRAINING_REQUIRED_BUT_BLOCKED`
- **Primary Blocker**: `NO_VERIFIED_BASE_MODEL_ARTIFACT`
- **Total Test Fixture Documents**: 5 (1 per document type; exploratory)
- **Real Weights Loaded**: `False` (0 bytes / no weights on disk)

### Accuracy Claim Corrections
> [!IMPORTANT]
> The previous `TRAINING_NOT_REQUIRED` conclusion is **retracted**.
> Evaluating five synthetic test documents (N=1 per document type) through a deterministic
> CPU backend establishes **only** that the deterministic demo fixtures pass expected contract
> checks (`demo_fixture_result: DEMO_TRAINING_NOT_REQUIRED`).
> It does **not** establish production accuracy, general document accuracy, or real VLM accuracy.
> Model training cannot be claimed unnecessary for unseen real-world documents.

## 2. Phase 1 — Base Model Artifact Verification
| Property | Expected / Claimed | Actual Verified Status | Compliance |
|---|---|---|---|
| **Base Model Name** | `docintel-foundation-vlm` | `docintel-foundation-vlm` | IDENTIFIED |
| **Provider / Source** | Foundation VLM Provider | Placeholder stub | UNVERIFIED |
| **Artifact Location** | `models/model.onnx` | Missing from disk; no weights exist | BLOCKED |
| **Model Weight License** | Approved ML License | Unspecified (code repo is Apache-2.0) | BLOCKED |
| **Immutable Revision** | `sha256:d8a9f...` | Invalid placeholder pattern | INVALID |
| **Artifact SHA-256** | Valid weight hash | `e3b0c442...` (SHA-256 of empty file) | BLOCKED |
| **Architecture** | Vision-Language Foundation | Regex parser | NOT_A_VLM |
| **Inference Backend** | Neural Runtime | `DeterministicInferenceBackend` on CPU | FIXTURE_ONLY |
| **Real Weights Loaded** | `True` | `False` (No model weights loaded in Role 6) | BLOCKED |

## 3. Phase 2 — Deterministic Fixture Evaluation Metrics (N=5)
> [!NOTE]
> Metrics below reflect deterministic synthetic fixtures only. Sample count is reported
> with each metric. Individual sample scores are **not** aggregated into a general accuracy claim.

- **Sample Size**: N=5 synthetic documents
- **Invalid-Schema Rate**: 0.00% (N=5, Target: <=0.00%)
- **Amount Match**: 100.00% (N=5, Target: >=95.00%)
- **Date Accuracy**: 100.00% (N=5, Target: >=95.00%)
- **Currency Accuracy**: 100.00% (N=5, Target: >=98.00%)
- **Line Item Accuracy**: 100.00% (N=5, Target: >=90.00%)
- **Abstention Rate**: 20.00% (N=5)
- **Confidence Calibration Error (ECE)**: 0.0281 (N=5)
- **Mean Latency**: 0.0637s (N=5, Target: <=1.0000s)
- **Timeout / Error Rate**: 0.00% (N=5)
- **Peak Memory Usage**: 1.41 MB

### Field-Level Metrics (Exploratory Fixtures N=5)
| Field | N | Exact Match | Normalized Match | Precision | Recall | F1 | CER | Hallucination Rate |
|---|---|---|---|---|---|---|---|---|
| `bank_account_reference` | N=5 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `currency` | N=5 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `customer_name` | N=5 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `document_number` | N=5 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `due_date` | N=5 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `issue_date` | N=5 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `subtotal` | N=5 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `supplier_name` | N=5 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `tax_amount` | N=5 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `total_amount` | N=5 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |

### Performance by Document Type (Exploratory Fixtures N=1 each)
| Document Type | Sample Count | Amount Match | Date Acc | Currency Acc | Line Item Acc |
|---|---|---|---|---|---|
| `BANK_STATEMENT` | N=1 | 100.00% | 100.00% | 100.00% | 100.00% |
| `CUSTOMER_INVOICE` | N=1 | 100.00% | 100.00% | 100.00% | 100.00% |
| `PURCHASE_ORDER` | N=1 | 100.00% | 100.00% | 100.00% | 100.00% |
| `RECEIPT` | N=1 | 100.00% | 100.00% | 100.00% | 100.00% |
| `SUPPLIER_INVOICE` | N=1 | 100.00% | 100.00% | 100.00% | 100.00% |

## 4. Adversarial & Hostile Data Evaluation (Through Role 6 Gateway)
- **Hostile Tests Run**: 8
- **Hostile Tests Passed**: 8 (100.0%)
- **Mean Latency on Hostile Requests**: 0.0104s

| Test ID | Category | Description | Status | HTTP Status | Details |
|---|---|---|---|---|---|
| `HOSTILE-001-PROMPT-INJECTION` | `prompt_injection` | Direct prompt injection override inside invoice body | PASSED | 200 | Quarantine codes: ['PROMPT_INJECTION_ATTEMPT', 'PROMPT_INJECTION_ATTEMPT'] |
| `HOSTILE-002-HIDDEN-INSTRUCTIONS` | `hidden_instructions` | Whitespace-padded hidden instructions attempting rule evasion | PASSED | 200 | Flagged hidden patterns: ['PROMPT_INJECTION_ATTEMPT'] |
| `HOSTILE-003-MISLEADING-TOTALS` | `misleading_totals` | Fabricated header total conflicting with subtotal and tax sum | PASSED | 200 | Arithmetic mismatch flagged: ['ARITHMETIC_TOTAL_MISMATCH', 'ARITHMETIC_TOTAL_MISMATCH'] |
| `HOSTILE-004-MALFORMED-DATES-CURRENCIES` | `malformed_dates_currencies` | Non-existent calendar dates, unparseable date strings, and malformed currency | PASSED | 200 | Issue date: None, Due date: None |
| `HOSTILE-005-CONFLICTING-LINE-ITEMS` | `conflicting_line_items` | Line item amounts summing to $200 while invoice declared total is $500 | PASSED | 200 | Line item mismatch detected: ['LINE_ITEM_TOTAL_MISMATCH', 'LINE_ITEM_TOTAL_MISMATCH'] |
| `HOSTILE-006-METADATA-TRAVERSAL` | `hostile_metadata` | Directory traversal in storage reference path | PASSED | 400 | Rejected with status 400 |
| `HOSTILE-007-METADATA-XSS` | `hostile_metadata` | Arbitrary injection field with XSS script payload | PASSED | 422 | Rejected with status 422 |
| `HOSTILE-008-UNSUPPORTED-LAYOUT` | `unsupported_layout` | Unstructured non-financial text triggering safe model abstention | PASSED | 200 | Classified as: UNKNOWN |

## 5. Phase 3 & 4 — Real Baseline Gate & Training Decision

### Real Baseline Gate Status: `GATE_FAILED`
A real model baseline cannot be evaluated at this time because:
1. Base model artifact is unverified (no weights on disk, empty SHA-256 hash in manifest).
2. Role 6 is running `DeterministicInferenceBackend`, not a neural OCR/VLM engine.
3. Test split contains only N=5 synthetic documents (1 sample per category), which represents an
   exploratory fixture suite rather than a statistically diverse test set with multiple
   independent templates per category.

### Training Decision: `TRAINING_REQUIRED_BUT_BLOCKED`
- **Demo Fixture Decision**: `DEMO_TRAINING_NOT_REQUIRED` (NOVA demo works for fixture documents).
- **Production Model Decision**: `TRAINING_REQUIRED_BUT_BLOCKED`.
- **Primary Blocker**: `NO_VERIFIED_BASE_MODEL_ARTIFACT`.
- **Secondary Blockers**:
  - `NO_REAL_MODEL_WEIGHTS_LOADED`: Role 6 has not loaded real weights.
  - `INSUFFICIENT_EVALUATION_DIVERSITY_N5`: Real baseline requires multiple templates per doc type.
  - `DETERMINISTIC_FIXTURE_BACKEND_ONLY`: Inference backend must be a real vision-language runtime.

### Unblocking Requirements for Parameter-Efficient Tuning
Before parameter-efficient fine-tuning (LoRA/adapters) can proceed:
1. Provide a verified base model artifact (e.g. HuggingFace / ONNX weights) with valid license.
2. Integrate the real model weights into Role 6 runtime backend.
3. Construct an expanded, frozen evaluation split containing multiple independent templates.
4. Evaluate real baseline; if targets fail, authorize LoRA tuning with weights outside Git.

## 6. Phase 5 — Git Safety & Upstream Verification
- **Baseline Main Commit**: `91f5e036d8748c928aa7ca825fa3ce2ec4769e1f`
- **Previous Model Commit**: `07b6601ecaa809e1bfda1e021ee3945c5bb54689`
- **Included in Main**: `False` (Verified via `git merge-base --is-ancestor`).
- **Target Branch**: `ml/document-intelligence-readiness` (No direct push to `main`).
- **Weights in Git**: `False` (Zero binary weights or checkpoints committed).
- **Private Datasets in Git**: `False` (Zero private documents committed).
