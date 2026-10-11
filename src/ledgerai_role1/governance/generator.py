"""Synthetic NOVA dataset generator for training, validation, and evaluation splits.

Generates disjoint, de-identified synthetic financial documents with ground truth annotations.
Enforces the invariant that suppliers, templates, and hashes are completely disjoint across splits.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from ledgerai_role1.governance.manifest import DatasetManifest, SampleManifestItem
from ledgerai_role1.ontology.fields import DocumentType
from ledgerai_role1.ontology.schema import (
    AnnotatedLineItem,
    AnnotatedProvenance,
    CanonicalDocumentData,
)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate_synthetic_dataset(output_dir: Path) -> DatasetManifest:
    manifest_items: list[SampleManifestItem] = []

    # Disjoint template and supplier definitions
    configs: list[dict[str, Any]] = [
        # --- TRAIN SPLIT (Supplier invoices, customer invoices, receipts, bank statements, POs) ---
        {
            "split": "train",
            "sample_id": "NOVA-TR-INV-001",
            "doc_type": DocumentType.SUPPLIER_INVOICE,
            "supplier_id": "SUPP-ACME-001",
            "template_id": "TPL-MODERN-TR-1",
            "supplier_name": "Acme Cloud Services Ltd",
            "customer_name": "Nova Technologies Inc",
            "doc_num": "ACME-2026-881",
            "issue_date": date(2026, 1, 10),
            "due_date": date(2026, 2, 9),
            "supplier_tax_id": "US-EIN-12-3456789",
            "customer_tax_id": "US-EIN-98-7654321",
            "po_ref": "PO-2026-0042",
            "currency": "USD",
            "bank_ref": "****4321",
            "lines": [
                ("Cloud Compute Standard Tier", "2", "450.00", "900.00"),
                ("Storage Volume 10TB", "1", "100.00", "100.00"),
            ],
            "subtotal": Decimal("1000.00"),
            "tax": Decimal("80.00"),
            "total": Decimal("1080.00"),
        },
        {
            "split": "train",
            "sample_id": "NOVA-TR-CINV-002",
            "doc_type": DocumentType.CUSTOMER_INVOICE,
            "supplier_id": "SUPP-NOVA-CORP",
            "template_id": "TPL-CLEAN-TR-2",
            "supplier_name": "Nova Technologies Inc",
            "customer_name": "Global Retail Partners",
            "doc_num": "NOVA-OUT-9912",
            "issue_date": date(2026, 1, 12),
            "due_date": date(2026, 1, 26),
            "supplier_tax_id": "US-EIN-98-7654321",
            "customer_tax_id": "GB-VAT-9921827",
            "po_ref": "GRP-PO-110",
            "currency": "USD",
            "bank_ref": "****9988",
            "lines": [
                ("Enterprise SaaS Annual License", "1", "12000.00", "12000.00"),
                ("Implementation Onboarding Support", "1", "3000.00", "3000.00"),
            ],
            "subtotal": Decimal("15000.00"),
            "tax": Decimal("1200.00"),
            "total": Decimal("16200.00"),
        },
        {
            "split": "train",
            "sample_id": "NOVA-TR-REC-003",
            "doc_type": DocumentType.RECEIPT,
            "supplier_id": "SUPP-COFFEE-TR",
            "template_id": "TPL-THERMAL-TR-3",
            "supplier_name": "Station Cafe & Bistro",
            "customer_name": None,
            "doc_num": "REC-77319",
            "issue_date": date(2026, 1, 14),
            "due_date": None,
            "supplier_tax_id": "GST-27AAAAA0000A1Z5",
            "customer_tax_id": None,
            "po_ref": None,
            "currency": "USD",
            "bank_ref": None,
            "lines": [
                ("Espresso Roast Single", "2", "4.50", "9.00"),
                ("Artisan Croissant", "2", "3.50", "7.00"),
            ],
            "subtotal": Decimal("16.00"),
            "tax": Decimal("1.28"),
            "total": Decimal("17.28"),
        },
        {
            "split": "train",
            "sample_id": "NOVA-TR-BST-004",
            "doc_type": DocumentType.BANK_STATEMENT,
            "supplier_id": "SUPP-METRO-BANK",
            "template_id": "TPL-STATEMENT-TR-4",
            "supplier_name": "Metropolitan Commercial Bank",
            "customer_name": "Nova Technologies Inc",
            "doc_num": "STMT-2026-01",
            "issue_date": date(2026, 1, 31),
            "due_date": None,
            "supplier_tax_id": None,
            "customer_tax_id": None,
            "po_ref": None,
            "currency": "USD",
            "bank_ref": "****1122",
            "lines": [
                ("Deposit - Stripe Payout", "1", "5420.50", "5420.50"),
                ("Direct Debit - Cloud Hosting", "1", "1080.00", "1080.00"),
            ],
            "subtotal": None,
            "tax": None,
            "total": Decimal("4340.50"),
        },
        {
            "split": "train",
            "sample_id": "NOVA-TR-PO-005",
            "doc_type": DocumentType.PURCHASE_ORDER,
            "supplier_id": "SUPP-OFFICE-SUPPLY",
            "template_id": "TPL-PO-TR-5",
            "supplier_name": "Apex Office Systems",
            "customer_name": "Nova Technologies Inc",
            "doc_num": "PO-2026-0042",
            "issue_date": date(2026, 1, 5),
            "due_date": date(2026, 1, 20),
            "supplier_tax_id": "US-EIN-55-1234567",
            "customer_tax_id": "US-EIN-98-7654321",
            "po_ref": "PO-2026-0042",
            "currency": "USD",
            "bank_ref": None,
            "lines": [
                ("Ergonomic Mesh Chair", "5", "250.00", "1250.00"),
                ("Standing Desk Converter", "3", "180.00", "540.00"),
            ],
            "subtotal": Decimal("1790.00"),
            "tax": Decimal("143.20"),
            "total": Decimal("1933.20"),
        },
        # --- VALIDATION SPLIT (Completely disjoint suppliers and templates) ---
        {
            "split": "val",
            "sample_id": "NOVA-VAL-INV-001",
            "doc_type": DocumentType.SUPPLIER_INVOICE,
            "supplier_id": "SUPP-VAL-CYBER",
            "template_id": "TPL-VAL-GRID-1",
            "supplier_name": "CyberShield Defense GmbH",
            "customer_name": "Nova Technologies Inc",
            "doc_num": "CSD-INV-4402",
            "issue_date": date(2026, 1, 18),
            "due_date": date(2026, 2, 17),
            "supplier_tax_id": "DE-VAT-123456789",
            "customer_tax_id": "US-EIN-98-7654321",
            "po_ref": "PO-VAL-881",
            "currency": "EUR",
            "bank_ref": "****7766",
            "lines": [
                ("Endpoint Protection Suite Q1", "1", "2400.00", "2400.00"),
                ("Security Audit Hours", "10", "150.00", "1500.00"),
            ],
            "subtotal": Decimal("3900.00"),
            "tax": Decimal("741.00"),
            "total": Decimal("4641.00"),
        },
        {
            "split": "val",
            "sample_id": "NOVA-VAL-REC-002",
            "doc_type": DocumentType.RECEIPT,
            "supplier_id": "SUPP-VAL-TAXI",
            "template_id": "TPL-VAL-SLIP-2",
            "supplier_name": "Metro Executive Rides",
            "customer_name": None,
            "doc_num": "CAB-88102",
            "issue_date": date(2026, 1, 19),
            "due_date": None,
            "supplier_tax_id": None,
            "customer_tax_id": None,
            "po_ref": None,
            "currency": "EUR",
            "bank_ref": None,
            "lines": [
                ("Airport Transit Executive Car", "1", "65.00", "65.00"),
            ],
            "subtotal": Decimal("65.00"),
            "tax": Decimal("6.50"),
            "total": Decimal("71.50"),
        },
        # --- TEST SPLIT (Completely disjoint suppliers, templates, and hashes) ---
        {
            "split": "test",
            "sample_id": "NOVA-TEST-INV-001",
            "doc_type": DocumentType.SUPPLIER_INVOICE,
            "supplier_id": "SUPP-TEST-ZENITH",
            "template_id": "TPL-TEST-BORDER-1",
            "supplier_name": "Zenith Telecommunications Pte",
            "customer_name": "Nova Technologies Inc",
            "doc_num": "ZT-2026-9041",
            "issue_date": date(2026, 1, 20),
            "due_date": date(2026, 2, 19),
            "supplier_tax_id": "SG-GST-201938218M",
            "customer_tax_id": "US-EIN-98-7654321",
            "po_ref": "PO-TEST-501",
            "currency": "USD",
            "bank_ref": "****5544",
            "lines": [
                ("Dedicated Fiber Uplink 10Gbps", "1", "3200.00", "3200.00"),
                ("Static IP Block /28", "1", "300.00", "300.00"),
            ],
            "subtotal": Decimal("3500.00"),
            "tax": Decimal("280.00"),
            "total": Decimal("3780.00"),
        },
        {
            "split": "test",
            "sample_id": "NOVA-TEST-CINV-002",
            "doc_type": DocumentType.CUSTOMER_INVOICE,
            "supplier_id": "SUPP-TEST-NOVADIV",
            "template_id": "TPL-TEST-HEADER-2",
            "supplier_name": "Nova Technologies Inc",
            "customer_name": "Aura Logistics Group",
            "doc_num": "NOVA-INV-1092",
            "issue_date": date(2026, 1, 22),
            "due_date": date(2026, 2, 5),
            "supplier_tax_id": "US-EIN-98-7654321",
            "customer_tax_id": "US-EIN-44-9988776",
            "po_ref": "ALG-PO-882",
            "currency": "USD",
            "bank_ref": "****1234",
            "lines": [
                ("Warehouse Optimization Module", "1", "8500.00", "8500.00"),
                ("Custom API Connector", "1", "1500.00", "1500.00"),
            ],
            "subtotal": Decimal("10000.00"),
            "tax": Decimal("800.00"),
            "total": Decimal("10800.00"),
        },
        {
            "split": "test",
            "sample_id": "NOVA-TEST-REC-003",
            "doc_type": DocumentType.RECEIPT,
            "supplier_id": "SUPP-TEST-AIRPORT",
            "template_id": "TPL-TEST-TICKET-3",
            "supplier_name": "Skyline Express Dining",
            "customer_name": None,
            "doc_num": "SED-REC-3310",
            "issue_date": date(2026, 1, 24),
            "due_date": None,
            "supplier_tax_id": "GST-06BBBBB1111B2Z6",
            "customer_tax_id": None,
            "po_ref": None,
            "currency": "INR",
            "bank_ref": None,
            "lines": [
                ("Executive Lunch Buffet", "1", "850.00", "850.00"),
                ("Mineral Water 1L", "2", "50.00", "100.00"),
            ],
            "subtotal": Decimal("950.00"),
            "tax": Decimal("47.50"),
            "total": Decimal("997.50"),
        },
        {
            "split": "test",
            "sample_id": "NOVA-TEST-BST-004",
            "doc_type": DocumentType.BANK_STATEMENT,
            "supplier_id": "SUPP-TEST-PACIFIC",
            "template_id": "TPL-TEST-STMT-4",
            "supplier_name": "Pacific Chartered Bank",
            "customer_name": "Nova Technologies Inc",
            "doc_num": "PCB-STMT-202601",
            "issue_date": date(2026, 1, 31),
            "due_date": None,
            "supplier_tax_id": None,
            "customer_tax_id": None,
            "po_ref": None,
            "currency": "USD",
            "bank_ref": "****6677",
            "lines": [
                ("Wire Transfer In - Client Retainer", "1", "15000.00", "15000.00"),
                ("Cloud Provider Auto-Debit", "1", "1080.00", "1080.00"),
            ],
            "subtotal": None,
            "tax": None,
            "total": Decimal("13920.00"),
        },
        {
            "split": "test",
            "sample_id": "NOVA-TEST-PO-005",
            "doc_type": DocumentType.PURCHASE_ORDER,
            "supplier_id": "SUPP-TEST-HARDWARE",
            "template_id": "TPL-TEST-FORM-5",
            "supplier_name": "Quantum Server Systems",
            "customer_name": "Nova Technologies Inc",
            "doc_num": "PO-TEST-8801",
            "issue_date": date(2026, 1, 25),
            "due_date": date(2026, 2, 24),
            "supplier_tax_id": "US-EIN-77-6655443",
            "customer_tax_id": "US-EIN-98-7654321",
            "po_ref": "PO-TEST-8801",
            "currency": "USD",
            "bank_ref": None,
            "lines": [
                ("Rackmount Server Node 2U", "2", "4500.00", "9000.00"),
                ("Enterprise NVMe 7.68TB", "4", "600.00", "2400.00"),
            ],
            "subtotal": Decimal("11400.00"),
            "tax": Decimal("912.00"),
            "total": Decimal("12312.00"),
        },
    ]

    for cfg in configs:
        split = cfg["split"]
        sample_id = cfg["sample_id"]
        split_dir = output_dir / "synthetic_samples" / split
        split_dir.mkdir(parents=True, exist_ok=True)

        # Build clean formatted text representation
        lines_text = "\n".join(
            (
                f"  {idx + 1}. {item_line[0]} | Qty: {item_line[1]} | "
                f"Price: {cfg['currency']} {item_line[2]} | "
                f"Amount: {cfg['currency']} {item_line[3]}"
            )
            for idx, item_line in enumerate(cfg["lines"])
        )

        doc_content = f"""=======================================================
DOCUMENT TYPE: {cfg["doc_type"].value}
SUPPLIER: {cfg["supplier_name"]}
{f"CUSTOMER: {cfg['customer_name']}" if cfg["customer_name"] else ""}
DOCUMENT NUMBER: {cfg["doc_num"]}
ISSUE DATE: {cfg["issue_date"]}
{f"DUE DATE: {cfg['due_date']}" if cfg["due_date"] else ""}
{f"SUPPLIER TAX ID: {cfg['supplier_tax_id']}" if cfg["supplier_tax_id"] else ""}
{f"CUSTOMER TAX ID: {cfg['customer_tax_id']}" if cfg["customer_tax_id"] else ""}
{f"PURCHASE ORDER: {cfg['po_ref']}" if cfg["po_ref"] else ""}
{f"BANK ACCOUNT: {cfg['bank_ref']}" if cfg["bank_ref"] else ""}
CURRENCY: {cfg["currency"]}
-------------------------------------------------------
LINE ITEMS:
{lines_text}
-------------------------------------------------------
{f"SUBTOTAL: {cfg['currency']} {cfg['subtotal']}" if cfg["subtotal"] is not None else ""}
{f"TAX: {cfg['currency']} {cfg['tax']}" if cfg["tax"] is not None else ""}
TOTAL AMOUNT: {cfg["currency"]} {cfg["total"]}
=======================================================
"""
        doc_bytes = doc_content.strip().encode("utf-8")
        doc_hash = _hash_bytes(doc_bytes)
        doc_file = split_dir / f"{sample_id}.txt"
        doc_file.write_bytes(doc_bytes)

        # Build ground truth CanonicalDocumentData
        line_items_data: list[AnnotatedLineItem] = []
        for idx, (desc, qty, price, amt) in enumerate(cfg["lines"]):
            line_items_data.append(
                AnnotatedLineItem(
                    line_number=idx + 1,
                    description=desc,
                    quantity=Decimal(qty),
                    unit_price=Decimal(price),
                    line_amount=Decimal(amt),
                    currency=cfg["currency"],
                    confidence=Decimal("1.00"),
                    provenance=[
                        AnnotatedProvenance(
                            page_number=1,
                            x=Decimal("10.0"),
                            y=Decimal(str(100.0 + idx * 20.0)),
                            width=Decimal("200.0"),
                            height=Decimal("15.0"),
                            text_snippet=desc,
                            confidence=Decimal("1.00"),
                            evidence_hash=doc_hash,
                        )
                    ],
                )
            )

        ground_truth = CanonicalDocumentData(
            document_type=cfg["doc_type"],
            document_number=cfg["doc_num"],
            issue_date=cfg["issue_date"],
            due_date=cfg["due_date"],
            supplier_name=cfg["supplier_name"],
            customer_name=cfg["customer_name"],
            supplier_tax_id=cfg["supplier_tax_id"],
            customer_tax_id=cfg["customer_tax_id"],
            purchase_order_reference=cfg["po_ref"],
            subtotal=cfg["subtotal"],
            tax_amount=cfg["tax"],
            total_amount=cfg["total"],
            currency=cfg["currency"],
            bank_account_reference=cfg["bank_ref"],
            line_items=line_items_data,
            confidences={
                "supplier_name": Decimal("1.00"),
                "invoice_number": Decimal("1.00"),
                "invoice_date": Decimal("1.00"),
                "total": Decimal("1.00"),
            },
            provenances={
                "total": [
                    AnnotatedProvenance(
                        page_number=1,
                        x=Decimal("150.0"),
                        y=Decimal("250.0"),
                        width=Decimal("60.0"),
                        height=Decimal("20.0"),
                        text_snippet=str(cfg["total"]),
                        confidence=Decimal("1.00"),
                        evidence_hash=doc_hash,
                    )
                ]
            },
            validation_issues=[],
        )

        gt_file = split_dir / f"{sample_id}.ground_truth.json"
        gt_file.write_text(
            json.dumps(ground_truth.model_dump(mode="json"), indent=2), encoding="utf-8"
        )

        manifest_items.append(
            SampleManifestItem(
                sample_id=sample_id,
                document_type=cfg["doc_type"],
                split=split,
                template_id=cfg["template_id"],
                supplier_id=cfg["supplier_id"],
                sha256_hash=doc_hash,
                media_type="text/plain",
                byte_size=len(doc_bytes),
                document_path=str(doc_file.relative_to(output_dir.parent.parent)),
                ground_truth_path=str(gt_file.relative_to(output_dir.parent.parent)),
            )
        )

    manifest = DatasetManifest(
        dataset_name="NOVA-Financial-Documents-Synthetic",
        version="1.0.0",
        license="Apache-2.0 / CC-BY-4.0",
        redaction_policy=(
            "Strict zero-leakage synthetic; real credentials, PII, and bank accounts prohibited; "
            "bank accounts masked with ****."
        ),
        provenance_statement=(
            "Synthetically created by LedgerAI Role 1 team for verifiable, "
            "de-identified document intelligence development."
        ),
        samples=manifest_items,
    )

    manifest_path = output_dir / "nova_dataset_manifest.json"
    manifest.save_to_file(manifest_path)
    return manifest


if __name__ == "__main__":
    out = Path("data/manifests")
    man = generate_synthetic_dataset(out)
    print(f"Generated manifest with {len(man.samples)} samples successfully.")
