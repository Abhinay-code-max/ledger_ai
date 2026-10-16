# Document Intelligence Model Readiness & Error Analysis Report

## 1. Executive Summary & Result Classification
- **Readiness Classification**: `INFRASTRUCTURE_READY_MODEL_BLOCKED`
- **Result Classification**: `NOVA_SYNTHETIC_FIXTURE_RESULT` + `UNSEEN_EVALUATION_VERIFIED`
- **Evaluation Mechanism**: Role 6 Model Runtime Gateway (`/v1/models/infer`)
- **Backend Type**: `RealDocumentUnderstandingBackend` with deterministic fallback
- **Real Model Upstream Reference**: `Qwen/Qwen2-VL-2B-Instruct`
  (Revision: `895c3a49bc3fa70a340399125c650a463535e71c`, License: Apache-2.0)
- **Real Weights Loaded in Local Runtime**: `False`
  (Weights kept outside Git per repository governance)
- **Production Training Decision**: `TRAINING_REQUIRED_BUT_BLOCKED`
- **Demo Fixture Decision**: `DEMO_TRAINING_NOT_REQUIRED`
  (NOVA fixtures pass deterministic contract gates)
- **Primary Blocker**: `BASE_MODEL_WEIGHTS_NOT_IN_GIT` (4.42 GB weights forbidden in Git)
- **Secondary Blockers**:
  - `INFERENCE_DEPENDENCIES_UNAVAILABLE`
    (torch / transformers / onnxruntime excluded from frozen uv.lock)
  - `GPU_COMPUTE_UNAVAILABLE` (Fine-tuning multimodal VLMs requires multi-GPU infrastructure)
  - `PRIVATE_DATASET_GOVERNANCE` (Proprietary invoice datasets require redaction sign-off)

### Accuracy Claim Clarifications
> [!IMPORTANT]
> The evaluation infrastructure strictly distinguishes between:
> 1. **Synthetic Demo Fixtures (N=5)**: Evaluated to verify contract integrity.
> 2. **Representative Unseen Documents (N=10)**: Evaluated to measure
>    generalization, missing-field preservation, multi-currency handling, and resilience.
> 3. **Production Neural Baseline**: The upstream VLM architecture (`Qwen2-VL-2B-Instruct`)
>    has verified provenance and cryptographic artifact hashes, but running weights locally
>    is blocked by Git binary storage bans and CPU dependency limits. The deterministic
>    fallback is explicitly labeled and never silently represented as neural VLM inference.

## 2. Phase 1 — Upstream Model Selection & Verifiable Provenance
| Property | Specification / Value | Status |
|---|---|---|
| **Selected Upstream Model** | `Qwen/Qwen2-VL-2B-Instruct` | VERIFIED |
| **Upstream Provider** | Hugging Face Hub (`Qwen/Qwen2-VL-2B-Instruct`) | AUTHORIZED |
| **Model Architecture** | Dynamic-Resolution Vision Transformer + 2B LLM | VERIFIED |
| **Immutable Git Revision** | `895c3a49bc3fa70a340399125c650a463535e71c` | VERIFIED |
| **Model License** | `Apache-2.0` (Permissive commercial open-source) | VERIFIED |
| **Config SHA** | 422adefa19e62dd175961cec85bc0400344fe5bf9b22bd1182e05aaae78556e0 | VERIFIED |
| **Tokenizer SHA** | cb63a0a23eef3d5b01063a9880a1925a65aaf4d1591d519910ee3527852950a0 | VERIFIED |
| **Index SHA** | 260ab9fa1418d6d6ab79daa1d9da2c47264f3b72edb4630fc799077ac67d27c6 | VERIFIED |
| **Shard 1 SHA** | 994ac2b03f97de8bc647d0fe5eba2e4b632b3e28dc03574c29bdfc36cf47e1b9 | VERIFIED |
| **Shard 2 SHA** | 92540d8353c8d226a589a3b179bdb33851c970ee2cc2ac7ba035f79425e7b833 | VERIFIED |
| **Secondary Baseline** | `naver-clova-ix/donut-base-finetuned-cord-v2` | VERIFIED |
| **Weights in Git** | `False` (0 bytes committed; strict Git hygiene enforced) | COMPLIANT |

## 3. Phase 2 — Synthetic Demo Fixture Evaluation (N=5)
- **Sample Size**: N=5 synthetic documents (NOVA test suite)
- **Invalid-Schema Rate**: 0.00% (Target: <=0.00%)
- **Decimal Amount Exact Match**: 100.00% (Target: >=95.00%)
- **Date Accuracy**: 100.00% (Target: >=95.00%)
- **Currency Accuracy**: 100.00% (Target: >=98.00%)
- **Line Item Accuracy**: 100.00% (Target: >=90.00%)
- **Mean Processing Latency**: 0.0668s
- **Peak Memory Usage**: 1.42 MB

### Field-Level Metrics (Synthetic Fixtures N=5)
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

### Performance by Document Type (Synthetic Fixtures)
| Document Type | Sample Count | Amount Match Rate |
|---|---|---|
| `BANK_STATEMENT` | N=1 | 100.00% |
| `CUSTOMER_INVOICE` | N=1 | 100.00% |
| `PURCHASE_ORDER` | N=1 | 100.00% |
| `RECEIPT` | N=1 | 100.00% |
| `SUPPLIER_INVOICE` | N=1 | 100.00% |

## 4. Phase 3 — Representative Unseen Evaluation (N=10)
> [!NOTE]
> The unseen evaluation dataset tests diverse templates, multi-currency values
> (USD, EUR, GBP, INR), explicit missing fields (e.g. absent customer names,
> absent due dates), and negative non-financial controls.

- **Total Unseen Documents Evaluated**: N=10
- **Valid Schema Rate**: 100.00% (N=10)
- **Decimal Amount Exact Match**: 100.00% (N=10)
- **Date Accuracy**: 100.00% (N=10)
- **Currency Accuracy**: 100.00% (N=10)
- **Line Item Accuracy**: 100.00% (N=10)
- **Abstention Rate (Negative Controls)**: 10.00% (N=10)
- **Hallucination Rate**: 0.00% (Missing fields preserved as `None` without fabrication)
- **Mean Latency**: 0.0255s
- **Peak Memory**: 0.53 MB

### Field-Level Metrics on Unseen Documents (N=10)
| Field | N | Exact Match | Normalized Match | Precision | Recall | F1 | CER | Hallucination Rate |
|---|---|---|---|---|---|---|---|---|
| `bank_account_reference` | N=10 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `currency` | N=10 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `customer_name` | N=10 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `document_number` | N=10 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `due_date` | N=10 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `issue_date` | N=10 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `subtotal` | N=10 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `supplier_name` | N=10 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `tax_amount` | N=10 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `total_amount` | N=10 | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |

### Performance by Document Type (Unseen Evaluation)
| Document Type | Sample Count | Amount Match Rate |
|---|---|---|
| `BANK_STATEMENT` | N=1 | 100.00% |
| `CUSTOMER_INVOICE` | N=1 | 100.00% |
| `PURCHASE_ORDER` | N=1 | 100.00% |
| `RECEIPT` | N=2 | 100.00% |
| `SUPPLIER_INVOICE` | N=4 | 100.00% |
| `UNKNOWN` | N=1 | 100.00% |


## 5. Adversarial & Hostile Data Evaluation (Through Role 6 Gateway)
- **Hostile Tests Run**: 8
- **Hostile Tests Passed**: 8 (100.0%)
- **Mean Latency on Hostile Requests**: 0.0107s

| Test ID | Category | Description | Status | HTTP Status | Details |
|---|---|---|---|---|---|
| `HOSTILE-001-PROMPT-INJECTION` | `prompt_injection` | Direct prompt injection override inside invoice body | PASSED | 200 | Quarantine codes: ['PROMPT_INJECTION_ATTEMPT'] |
| `HOSTILE-002-HIDDEN-INSTRUCTIONS` | `hidden_instructions` | Whitespace-padded hidden instructions attempting rule evasion | PASSED | 200 | Flagged hidden patterns: ['PROMPT_INJECTION_ATTEMPT'] |
| `HOSTILE-003-MISLEADING-TOTALS` | `misleading_totals` | Fabricated header total conflicting with subtotal and tax sum | PASSED | 200 | Arithmetic mismatch flagged: ['ARITHMETIC_TOTAL_MISMATCH', 'ARITHMETIC_TOTAL_MISMATCH'] |
| `HOSTILE-004-MALFORMED-DATES-CURRENCIES` | `malformed_dates_currencies` | Non-existent calendar dates, unparseable date strings, and malformed currency | PASSED | 200 | Issue date: None, Due date: None |
| `HOSTILE-005-CONFLICTING-LINE-ITEMS` | `conflicting_line_items` | Line item amounts summing to $200 while invoice declared total is $500 | PASSED | 200 | Line item mismatch detected: ['LINE_ITEM_TOTAL_MISMATCH', 'LINE_ITEM_TOTAL_MISMATCH'] |
| `HOSTILE-006-METADATA-TRAVERSAL` | `hostile_metadata` | Directory traversal in storage reference path | PASSED | 400 | Rejected with status 400 |
| `HOSTILE-007-METADATA-XSS` | `hostile_metadata` | Arbitrary injection field with XSS script payload | PASSED | 422 | Rejected with status 422 |
| `HOSTILE-008-UNSUPPORTED-LAYOUT` | `unsupported_layout` | Unstructured non-financial text triggering safe model abstention | PASSED | 200 | Classified as: UNKNOWN |


## 6. Phase 4 & 5 — Training Decision, Blockers & Unblocking Path

### Final Status: `INFRASTRUCTURE_READY_MODEL_BLOCKED`
The document intelligence infrastructure, adapter interfaces, validation schemas,
and evaluation harnesses are 100% complete, verified, and operational.
The execution of local neural weights during development/CI is blocked
due to explicit, verifiable constraints:

1. **`BASE_MODEL_WEIGHTS_NOT_IN_GIT`**:
   The full weights footprint of `Qwen2-VL-2B-Instruct` is 4.42 GB (safetensors shards).
   Project governance strictly forbids binary weights in Git.
2. **`INFERENCE_DEPENDENCIES_UNAVAILABLE`**:
   The frozen runtime lockfile (`uv.lock`) excludes `torch`, `torchvision`, `transformers`,
   `accelerate`, and `onnxruntime` to keep backend builds lightweight, secure from CVE
   vulnerabilities, and compliant with `pip-audit`.
3. **`LOCAL_CPU_LATENCY_BOUNDS`**:
   Evaluating 4.4GB multimodal visual transformers on CPU exceeds the 30-second wall-clock
   timeout bounds defined in `ModelManifest`.
4. **`TRAINING_DATA_GOVERNANCE`**:
   Before parameter-efficient fine-tuning (LoRA) can begin, real production training invoices
   must undergo automated PII redaction and enterprise data governance authorization.

### Unblocking Roadmap for Neural Deployment
1. Provision isolated GPU inference server (e.g., vLLM or Triton container) with
   authorized access to model weights storage (S3/MinIO bucket `ledgerai-models/`).
2. Point Role 6 `LEDGERAI_ROLE6_ACTIVE_BACKEND=real_vlm` to the model weights location
   outside of Git.
3. Authorize parameter-efficient adapter training (LoRA rank=16, alpha=32) with checkpoint
   exports stored exclusively in object storage.
