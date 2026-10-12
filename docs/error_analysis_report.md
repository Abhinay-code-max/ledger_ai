# Model Evaluation and Error Analysis Report: Role 1 Document Intelligence

## 1. Executive Summary
- **Total Test Documents**: 5
- **Invalid-Schema Rate**: 0.00% (Target: <=0.00%)
- **Decimal Amount Exact Match**: 100.00% (Target: >=95.00%)
- **Date Accuracy**: 100.00% (Target: >=95.00%)
- **Currency Accuracy**: 100.00% (Target: >=98.00%)
- **Line Item Extraction Accuracy**: 100.00% (Target: >=90.00%)
- **Abstention / Unsupported Rate**: 20.00%
- **Confidence Calibration Error (ECE)**: 0.0388
- **Mean Processing Latency**: 0.0194s
- **Peak Memory Usage**: 0.22 MB

## 2. Field-Level Metrics
| Field | Exact Match | Normalized Match | Precision | Recall | F1 | CER | Hallucination Rate |
|---|---|---|---|---|---|---|---|
| `bank_account_reference` | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `currency` | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `customer_name` | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `document_number` | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `due_date` | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `issue_date` | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `subtotal` | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `supplier_name` | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `tax_amount` | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |
| `total_amount` | 100.00% | 100.00% | 1.00 | 1.00 | 1.00 | 0.0000 | 0.00% |

## 3. Performance by Document Type
| Document Type | Samples Evaluated | Amount Match Rate |
|---|---|---|
| `BANK_STATEMENT` | 1 | 100.00% |
| `CUSTOMER_INVOICE` | 1 | 100.00% |
| `PURCHASE_ORDER` | 1 | 100.00% |
| `RECEIPT` | 1 | 100.00% |
| `SUPPLIER_INVOICE` | 1 | 100.00% |

## 4. Acceptance Criteria Decision
**Fine-tuning Status**: **NOT JUSTIFIED / SKIPPED**.

The deterministic + pretrained baseline successfully met or exceeded all pre-declared acceptance targets across all test-set document types. Decimal amount accuracy achieved 100.00%, currency accuracy achieved 100.00%, date accuracy achieved 100.00%, and invalid-schema rate was 0.00%. Zero prompt injections succeeded. Therefore, per the Model Strategy sequence, unnecessary parameter fine-tuning is avoided to preserve deterministic precision, prevent overfitting, and eliminate model drift.
