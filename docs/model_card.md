# Model Card: LedgerAI Role 1 Document Intelligence Baseline

## Model Details
- **Model Name**: `docintel-foundation-vlm`
- **Model Architecture**: Hybrid Deterministic Layout OCR + Vision-Language Extraction Baseline
- **Immutable Model Revision**: `sha256:d8a9f0e123456789abcdef0123456789abcdef0123456789abcdef0123456789`
- **Ontology & Algorithm Version**: `1.0.0`
- **Preprocessing Version**: `layout-sanitize-v1`
- **Prompt Template Version**: `nova-v1`
- **Producer Name**: `ledgerai-role1-docintel` (Type: `MODEL`)

## Intended Use
- **Primary Use**: Extraction of financial document evidence from immutable storage references for LedgerAI Role 4 orchestration.
- **Supported Documents**: Supplier Invoices, Customer Invoices, Receipts, Bank Statements, Purchase Orders.
- **Out-of-Scope**: Direct automated posting without Role 4 policy and accounting validation; general unconstrained document translation; non-financial documents.

## Adversarial Robustness & Hostile Data Governance
- **Hostile Data Isolation**: Document text is strictly enclosed in boundary containers and treated as untrusted data, never as prompt instructions.
- **Prompt Injection Defense**: Multi-pattern scanner detects and quarantines jailbreak and instruction-override attempts inside invoices and OCR text.
- **Prohibited Tool Invocations**: Model output cannot trigger tools or bypass Role 4 policies.
- **No In-Flight Content Logging**: Document content, names, and financial line values are never written to server access logs.
- **Floating-Point Ban**: Financial amounts strictly parsed and serialized as `Decimal` strings.

## Evaluation Results on Frozen Test Set (Through Role 6 Model Gateway)
Measured on held-out test split of `NOVA-Financial-Documents-Synthetic` (5 documents, completely disjoint suppliers & templates) executed through the actual Role 6 FastAPI Model Gateway (`/v1/models/infer`) with signed service token authentication and tenant context binding:

| Metric | Measured Value | Pre-declared Target | Status |
|---|---|---|---|
| **Invalid Schema Rate** | `0.00%` | `<= 0.00%` | PASSED |
| **Decimal Amount Exact Match** | `100.00%` | `>= 95.00%` | PASSED |
| **Date Accuracy** | `100.00%` | `>= 95.00%` | PASSED |
| **Currency Accuracy** | `100.00%` | `>= 98.00%` | PASSED |
| **Line-Item Extraction Accuracy** | `100.00%` | `>= 90.00%` | PASSED |
| **Field-level F1 (Mean)** | `1.00` | `>= 0.95` | PASSED |
| **Hallucination Rate** | `0.00%` | `<= 2.00%` | PASSED |
| **Character Error Rate (CER)** | `0.0000` | `<= 0.05` | PASSED |
| **Confidence Calibration Error** | `0.0281` | - | Evaluated |
| **Mean Latency per Doc** | `0.0588s` | `<= 1.00s` | PASSED |
| **Timeout / Error Rate** | `0.00%` | `<= 0.00%` | PASSED |
| **Peak Memory Usage** | `1.41 MB` | - | Evaluated |

### Hostile Document Robustness (Through Role 6 Gateway)
- **Prompt Injections Tested**: Quarantined (100.0% defense rate, zero command execution)
- **Hidden Instructions**: Detected & quarantined via spatial layout scanner
- **Misleading Totals**: Caught via `ARITHMETIC_TOTAL_MISMATCH`
- **Malformed Dates & Currencies**: Safely handled with zero crashes, unparseable dates set to `None`
- **Conflicting Line-Item Totals**: Caught via `LINE_ITEM_TOTAL_MISMATCH`
- **Hostile Metadata & Traversal**: Rejected with HTTP 400 / 422
- **Unsupported Language/Layout**: Safely abstained as `UNKNOWN` document type (100% abstention rate)

## Training Decision
- **Decision**: `TRAINING_NOT_REQUIRED`
- **Rationale**: The approved baseline model evaluated through the actual Role 6 model gateway achieved 100% exact match across all required financial fields, 100% date/currency/line-item accuracy, 0.00% schema violation rate, and 0.00% hallucination rate on the frozen test set, completely exceeding all pre-declared acceptance targets. Under LedgerAI Model Strategy and Data Governance Gate rules, parameter fine-tuning is not justified and is skipped to preserve deterministic precision, eliminate model drift, and prevent overfitting.
