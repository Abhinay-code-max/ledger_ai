# Model Card: LedgerAI Role 1 Document Intelligence

## 1. Model Details
- **Model Identifier**: `docintel-foundation-vlm`
- **Upstream Reference Architecture**: `Qwen/Qwen2-VL-2B-Instruct`
- **Upstream Authorized Provider**: Qwen Team / Hugging Face Hub (`https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct`)
- **Upstream Immutable Revision**: `895c3a49bc3fa70a340399125c650a463535e71c`
- **License**: `Apache-2.0` (Permissive commercial open-source)
- **Secondary Benchmark Reference**: `naver-clova-ix/donut-base-finetuned-cord-v2` (Revision: `8003d433...`, License: `MIT`)
- **Verified Upstream Artifact Checksums**:
  - `config.json`: `422adefa19e62dd175961cec85bc0400344fe5bf9b22bd1182e05aaae78556e0` (1,196 bytes)
  - `tokenizer.json`: `cb63a0a23eef3d5b01063a9880a1925a65aaf4d1591d519910ee3527852950a0` (7,029,741 bytes)
  - `model.safetensors.index.json`: `260ab9fa1418d6d6ab79daa1d9da2c47264f3b72edb4630fc799077ac67d27c6`
  - `model-00001-of-00002.safetensors`: `994ac2b03f97de8bc647d0fe5eba2e4b632b3e28dc03574c29bdfc36cf47e1b9` (3,988,609,112 bytes)
  - `model-00002-of-00002.safetensors`: `92540d8353c8d226a589a3b179bdb33851c970ee2cc2ac7ba035f79425e7b833` (429,441,656 bytes)
- **Local Runtime Backend**: `RealDocumentUnderstandingBackend` with explicitly labeled `cpu-deterministic-fallback`
- **Ontology & Algorithm Version**: `1.0.0`
- **Preprocessing Version**: `v1.0.0`
- **Producer Name**: `ledgerai-role6-docintel-gateway` (Type: `MODEL`)

## 2. Intended Use
- **Primary Use**: Extraction of financial document evidence from immutable storage references for LedgerAI Role 4 orchestration.
- **Supported Documents**: Supplier Invoices, Customer Invoices, Receipts, Bank Statements, Purchase Orders.
- **Out-of-Scope**: Direct automated posting without Role 4 policy and accounting validation; general unconstrained document translation; non-financial documents (which trigger safe model abstention `UNKNOWN`).

## 3. Adversarial Robustness & Hostile Data Governance
- **Hostile Data Isolation**: Document text is strictly enclosed in boundary containers and treated as untrusted data, never as prompt instructions.
- **Prompt Injection Defense**: Scanner detects and quarantines jailbreak and instruction-override attempts inside invoice content (`PROMPT_INJECTION_ATTEMPT`).
- **Missing Field Preservation**: Missing fields in document text (e.g., absent customer name on receipts, unstated due dates) are preserved as `None` without hallucination.
- **Arithmetic Cross-Validation**: Validates that `subtotal + tax_amount == total_amount` and line-item totals match declared document headers. Mismatches are flagged as `ARITHMETIC_TOTAL_MISMATCH` or `LINE_ITEM_TOTAL_MISMATCH`.
- **Bounded Inference**: Hard bounds on request bytes (10MB), page count (20 pages), and wall-clock execution timeout (30.0s).
- **No In-Flight Content Logging**: Document content, customer names, and financial line values are never written to server access logs.
- **Floating-Point Ban**: Financial amounts strictly parsed and serialized as `Decimal` strings.

## 4. Evaluation Results

### Synthetic Demo Fixtures (N=5)
| Metric | Measured Value | Pre-declared Target | Status |
|---|---|---|---|
| **Invalid Schema Rate** | `0.00%` | `<= 0.00%` | PASSED |
| **Decimal Amount Exact Match** | `100.00%` | `>= 95.00%` | PASSED |
| **Date Accuracy** | `100.00%` | `>= 95.00%` | PASSED |
| **Currency Accuracy** | `100.00%` | `>= 98.00%` | PASSED |
| **Line-Item Extraction Accuracy** | `100.00%` | `>= 90.00%` | PASSED |
| **Mean Latency per Doc** | `0.0623s` | `<= 1.00s` | PASSED |

### Representative Unseen Evaluation Set (N=10)
| Metric | Measured Value | Evaluation Invariant | Status |
|---|---|---|---|
| **Document Count** | `10` | Diverse multi-currency & missing-field samples | EVALUATED |
| **Valid Schema Rate** | `100.00%` | Must conform to canonical schema | PASSED |
| **Decimal Amount Exact Match** | `100.00%` | Exact match on declared totals | PASSED |
| **Missing Field Preservation** | `100.00%` | Zero hallucination on absent fields | PASSED |
| **Abstention Rate (Negative Control)** | `10.00%` | Non-financial text classified as UNKNOWN | PASSED |
| **Hostile Test Pass Rate** | `8/8 (100.0%)` | Injection, malformed data, traversal | PASSED |
| **Mean Latency per Doc** | `0.0267s` | Bounded execution | PASSED |

## 5. Model Readiness Classification & Training Decision
- **Model Readiness Status**: `INFRASTRUCTURE_READY_MODEL_BLOCKED`
- **Training Decision**: `TRAINING_REQUIRED_BUT_BLOCKED` (Production VLM) / `DEMO_TRAINING_NOT_REQUIRED` (Synthetic Fixtures)
- **Blockers**:
  1. `BASE_MODEL_WEIGHTS_NOT_IN_GIT`: The 4.42 GB weights footprint of `Qwen2-VL-2B-Instruct` is barred from Git by project storage policy.
  2. `INFERENCE_DEPENDENCIES_UNAVAILABLE`: The frozen Python runtime excludes `torch`, `torchvision`, and `transformers` to maintain deterministic, lightweight, CVE-audited CI builds.
  3. `GPU_COMPUTE_UNAVAILABLE`: Fine-tuning multimodal visual language models requires multi-GPU infrastructure.
  4. `PRIVATE_DATASET_GOVERNANCE`: Production fine-tuning requires enterprise data redaction and governance approval.
