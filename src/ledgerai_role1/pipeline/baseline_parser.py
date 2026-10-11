"""Deterministic OCR and regex/spatial layout baseline extractor."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ledgerai_contracts.v1.common import ValidationIssue
from ledgerai_role1.ontology.fields import DocumentType
from ledgerai_role1.ontology.schema import (
    AnnotatedLineItem,
    AnnotatedProvenance,
    CanonicalDocumentData,
)
from ledgerai_role1.pipeline.layout_ocr import DocumentLayoutAnalyzer
from ledgerai_role1.pipeline.provenance import compute_evidence_hash


class DeterministicBaselineExtractor:
    """Extracts financial fields deterministically from document text and layout tokens."""

    def __init__(self) -> None:
        self.analyzer = DocumentLayoutAnalyzer()

    def extract(
        self, document_bytes: bytes, *, media_type: str = "text/plain"
    ) -> CanonicalDocumentData:
        pages = self.analyzer.analyze(document_bytes, media_type=media_type)
        full_text = "\n".join(p.raw_text for p in pages)
        doc_hash = compute_evidence_hash(document_bytes)

        validation_issues: list[ValidationIssue] = []

        # Check prompt injection security flag
        for page in pages:
            if page.has_prompt_injection:
                for warn in page.injection_warnings:
                    validation_issues.append(
                        ValidationIssue(
                            code="PROMPT_INJECTION_ATTEMPT",
                            message=(
                                f"Adversarial prompt injection detected on "
                                f"page {page.page_number}: {warn}"
                            ),
                            field="document_content",
                            severity="ERROR",
                        )
                    )

        # 1. Document Type Detection
        doc_type = DocumentType.UNKNOWN
        if re.search(r"(?i)\bSUPPLIER INVOICE\b", full_text):
            doc_type = DocumentType.SUPPLIER_INVOICE
        elif re.search(r"(?i)\bCUSTOMER INVOICE\b", full_text):
            doc_type = DocumentType.CUSTOMER_INVOICE
        elif re.search(r"(?i)\bRECEIPT\b", full_text):
            doc_type = DocumentType.RECEIPT
        elif re.search(r"(?i)\bBANK STATEMENT\b", full_text):
            doc_type = DocumentType.BANK_STATEMENT
        elif re.search(r"(?i)\bPURCHASE ORDER\b", full_text):
            doc_type = DocumentType.PURCHASE_ORDER
        elif re.search(r"(?i)\bINVOICE\b", full_text):
            doc_type = DocumentType.SUPPLIER_INVOICE

        # Helper to search regex and locate token provenance
        def find_field(patterns: list[str]) -> tuple[str | None, list[AnnotatedProvenance]]:
            for pat in patterns:
                m = re.search(pat, full_text, re.MULTILINE)
                if m:
                    val = m.group(1).strip()
                    # Find token bounding box
                    provs: list[AnnotatedProvenance] = []
                    for page in pages:
                        for token in page.tokens:
                            if val in token.text:
                                provs.append(
                                    AnnotatedProvenance(
                                        page_number=token.page,
                                        x=token.x,
                                        y=token.y,
                                        width=token.width,
                                        height=token.height,
                                        text_snippet=token.text,
                                        confidence=token.confidence,
                                        evidence_hash=doc_hash,
                                    )
                                )
                                break
                        if provs:
                            break
                    if not provs:
                        provs.append(
                            AnnotatedProvenance(
                                page_number=1,
                                x=Decimal("20.0"),
                                y=Decimal("50.0"),
                                width=Decimal("100.0"),
                                height=Decimal("15.0"),
                                text_snippet=val,
                                confidence=Decimal("0.90"),
                                evidence_hash=doc_hash,
                            )
                        )
                    return val, provs
            return None, []

        # 2. Key Fields Extraction
        doc_num, doc_num_prov = find_field(
            [
                r"(?i)DOCUMENT NUMBER:\s*([A-Za-z0-9-_]+)",
                r"(?i)INVOICE NUMBER:\s*([A-Za-z0-9-_]+)",
                r"(?i)INVOICE #\s*([A-Za-z0-9-_]+)",
                r"(?i)REC #\s*([A-Za-z0-9-_]+)",
                r"(?i)PO NUMBER:\s*([A-Za-z0-9-_]+)",
            ]
        )

        supp_name, supp_prov = find_field(
            [
                r"(?i)SUPPLIER:\s*([^\n\r]+)",
                r"(?i)VENDOR:\s*([^\n\r]+)",
                r"(?i)MERCHANT:\s*([^\n\r]+)",
                r"(?i)BANK:\s*([^\n\r]+)",
            ]
        )

        cust_name, cust_prov = find_field(
            [
                r"(?i)CUSTOMER:\s*([^\n\r]+)",
                r"(?i)CLIENT:\s*([^\n\r]+)",
                r"(?i)BILL TO:\s*([^\n\r]+)",
            ]
        )

        supp_tax, supp_tax_prov = find_field(
            [
                r"(?i)SUPPLIER TAX ID:\s*([A-Za-z0-9-_]+)",
                r"(?i)GSTIN:\s*([A-Za-z0-9-_]+)",
                r"(?i)VAT ID:\s*([A-Za-z0-9-_]+)",
                r"(?i)EIN:\s*([A-Za-z0-9-_]+)",
            ]
        )

        cust_tax, cust_tax_prov = find_field(
            [
                r"(?i)CUSTOMER TAX ID:\s*([A-Za-z0-9-_]+)",
                r"(?i)CLIENT VAT:\s*([A-Za-z0-9-_]+)",
            ]
        )

        po_ref, po_prov = find_field(
            [
                r"(?i)PURCHASE ORDER:\s*([A-Za-z0-9-_]+)",
                r"(?i)PO REF:\s*([A-Za-z0-9-_]+)",
            ]
        )

        bank_ref, bank_prov = find_field(
            [
                r"(?i)BANK ACCOUNT:\s*([A-Za-z0-9-_\*]+)",
                r"(?i)ACCOUNT NUMBER:\s*([A-Za-z0-9-_\*]+)",
                r"(?i)ACCT:\s*([A-Za-z0-9-_\*]+)",
            ]
        )

        # Currency
        curr_raw, _ = find_field(
            [
                r"(?i)CURRENCY:\s*([A-Z]{3})",
                r"\b(USD|EUR|GBP|INR|CAD|AUD)\b",
            ]
        )
        currency = curr_raw if curr_raw and len(curr_raw) == 3 else "USD"

        # Dates
        def parse_date(date_str: str | None) -> date | None:
            if not date_str:
                return None
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_str)
            if m:
                try:
                    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    return None
            return None

        issue_raw, issue_prov = find_field(
            [
                r"(?i)ISSUE DATE:\s*(\d{4}-\d{2}-\d{2})",
                r"(?i)DATE:\s*(\d{4}-\d{2}-\d{2})",
                r"(?i)INVOICE DATE:\s*(\d{4}-\d{2}-\d{2})",
            ]
        )
        issue_date = parse_date(issue_raw)

        due_raw, due_prov = find_field(
            [
                r"(?i)DUE DATE:\s*(\d{4}-\d{2}-\d{2})",
                r"(?i)PAYMENT DUE:\s*(\d{4}-\d{2}-\d{2})",
            ]
        )
        due_date = parse_date(due_raw)

        # Money values
        def parse_amount(val_str: str | None) -> Decimal | None:
            if not val_str:
                return None
            cleaned = re.sub(r"[^\d.-]", "", val_str)
            try:
                return Decimal(cleaned)
            except (InvalidOperation, ValueError):
                return None

        subtotal_raw, subtotal_prov = find_field(
            [
                r"(?i)SUBTOTAL:\s*(?:[A-Z]{3}\s*)?([0-9,.]+)",
                r"(?i)NET AMOUNT:\s*(?:[A-Z]{3}\s*)?([0-9,.]+)",
            ]
        )
        subtotal = parse_amount(subtotal_raw)

        tax_raw, tax_prov = find_field(
            [
                r"(?i)TAX:\s*(?:[A-Z]{3}\s*)?([0-9,.]+)",
                r"(?i)VAT:\s*(?:[A-Z]{3}\s*)?([0-9,.]+)",
                r"(?i)GST:\s*(?:[A-Z]{3}\s*)?([0-9,.]+)",
            ]
        )
        tax = parse_amount(tax_raw)

        total_raw, total_prov = find_field(
            [
                r"(?i)TOTAL AMOUNT:\s*(?:[A-Z]{3}\s*)?([0-9,.]+)",
                r"(?i)TOTAL:\s*(?:[A-Z]{3}\s*)?([0-9,.]+)",
                r"(?i)AMOUNT DUE:\s*(?:[A-Z]{3}\s*)?([0-9,.]+)",
                r"(?i)BALANCE:\s*(?:[A-Z]{3}\s*)?([0-9,.]+)",
            ]
        )
        total = parse_amount(total_raw)

        # Line items extraction
        line_items: list[AnnotatedLineItem] = []
        # Match pattern: 1. Description | Qty: 2 | Price: USD 450.00 | Amount: USD 900.00
        line_pattern = re.compile(
            r"^\s*(\d+)\.\s*([^|]+)\|\s*Qty:\s*([0-9.]+)\s*\|\s*Price:\s*(?:[A-Z]{3}\s*)?([0-9.]+)\s*\|\s*Amount:\s*(?:[A-Z]{3}\s*)?([0-9.]+)",
            re.MULTILINE,
        )
        for idx, m in enumerate(line_pattern.finditer(full_text), start=1):
            line_no = int(m.group(1))
            desc = m.group(2).strip()
            qty = Decimal(m.group(3).strip())
            price = Decimal(m.group(4).strip())
            amt = Decimal(m.group(5).strip())
            line_items.append(
                AnnotatedLineItem(
                    line_number=line_no,
                    description=desc,
                    quantity=qty,
                    unit_price=price,
                    line_amount=amt,
                    currency=currency,
                    confidence=Decimal("0.98"),
                    provenance=[
                        AnnotatedProvenance(
                            page_number=1,
                            x=Decimal("20.0"),
                            y=Decimal(str(100.0 + idx * 20.0)),
                            width=Decimal("200.0"),
                            height=Decimal("15.0"),
                            text_snippet=desc,
                            confidence=Decimal("0.98"),
                            evidence_hash=doc_hash,
                        )
                    ],
                )
            )

        provenances: dict[str, list[AnnotatedProvenance]] = {}
        confidences: dict[str, Decimal] = {}

        if supp_name:
            provenances["supplier_name"] = supp_prov
            confidences["supplier_name"] = Decimal("0.98")
        if cust_name:
            provenances["customer_name"] = cust_prov
            confidences["customer_name"] = Decimal("0.98")
        if doc_num:
            provenances["invoice_number"] = doc_num_prov
            confidences["invoice_number"] = Decimal("0.98")
        if issue_date:
            provenances["invoice_date"] = issue_prov
            confidences["invoice_date"] = Decimal("0.98")
        if due_date:
            provenances["due_date"] = due_prov
            confidences["due_date"] = Decimal("0.98")
        if total is not None:
            provenances["total"] = total_prov
            confidences["total"] = Decimal("0.98")
        if subtotal is not None:
            provenances["subtotal"] = subtotal_prov
            confidences["subtotal"] = Decimal("0.98")
        if tax is not None:
            provenances["tax"] = tax_prov
            confidences["tax"] = Decimal("0.98")

        return CanonicalDocumentData(
            document_type=doc_type,
            document_number=doc_num,
            issue_date=issue_date,
            due_date=due_date,
            supplier_name=supp_name,
            customer_name=cust_name,
            supplier_tax_id=supp_tax,
            customer_tax_id=cust_tax,
            purchase_order_reference=po_ref,
            subtotal=subtotal,
            tax_amount=tax,
            total_amount=total,
            currency=currency,
            bank_account_reference=bank_ref,
            line_items=line_items,
            confidences=confidences,
            provenances=provenances,
            validation_issues=validation_issues,
        )
