# Dataset Card: NOVA Synthetic Financial Document Intelligence Dataset

## Summary
The **NOVA Synthetic Financial Document Intelligence Dataset** is a strictly synthetic, de-identified evaluation and training benchmark designed for LedgerAI Role 1 (Document Intelligence). It encompasses five core financial document types in the NOVA vertical slice:
1. Supplier Invoices (`SUPPLIER_INVOICE`)
2. Customer Invoices (`CUSTOMER_INVOICE`)
3. Receipts (`RECEIPT`)
4. Bank Statements (`BANK_STATEMENT`)
5. Purchase Orders (`PURCHASE_ORDER`)

## Governance and Licensing
- **License**: Apache-2.0 / CC-BY-4.0
- **Redistribution Limitations**: Public synthetic data. Commercial and testing use permitted without restriction. No proprietary customer data or production credentials may be added.
- **Redaction & PII Safety**: Strictly synthetic data. No real personal identifiers, SSNs, credit cards, or customer bank accounts. Bank account references are limited to the masked suffix format (`****XXXX`).

## Split Isolation Policy
To guarantee robust out-of-distribution evaluation and avoid data snooping:
- **Supplier Isolation**: Suppliers present in the `train` split are completely disjoint from suppliers in the `val` and `test` splits.
- **Template Isolation**: Visual and structural document templates in `train` do not appear in `val` or `test`.
- **Hash Uniqueness**: Exact and augmented document hashes (SHA-256) are strictly verified for non-overlap.
- **Verification Tool**: Built-in verification via `ledgerai_role1.governance.split.verify_split_integrity`.

## Ontology and Label Definitions
Annotations strictly conform to `src/ledgerai_role1/ontology`:
- `document_type`: Enum of standard financial document categories.
- `document_number`: Unique invoice/receipt/statement/order identifier.
- `issue_date` / `due_date`: Standard ISO-8601 calendar dates (`YYYY-MM-DD`).
- `supplier_name` / `customer_name`: Plain text entity names.
- `supplier_tax_id` / `customer_tax_id`: Tax registration numbers (e.g., GSTIN, EIN, VAT).
- `purchase_order_reference`: Cross-referencing purchase order code.
- `subtotal`, `tax_amount`, `total_amount`: Exact `Decimal` values; floating-point numbers are strictly forbidden.
- `currency`: ISO 4217 three-letter currency code (e.g. `USD`, `EUR`, `INR`).
- `bank_account_reference`: Masked bank account (`****1234`).
- `line_items`: Array of items comprising `line_number`, `description`, `quantity`, `unit_price`, and `line_amount`.
- `provenance`: Spatial coordinates (`x`, `y`, `width`, `height`), page numbers, and SHA-256 evidence hashes.

## Dataset Manifest
The dataset manifest is version-controlled at `data/manifests/nova_dataset_manifest.json`, storing SHA-256 digests and file metadata for every sample. Large raw blobs and model weights are explicitly excluded from Git tracking.
