"""Tests for data governance, redaction, manifests, and split integrity."""

from __future__ import annotations

from pathlib import Path

import pytest

from ledgerai_role1.governance.manifest import DatasetManifest
from ledgerai_role1.governance.redaction import (
    assert_safe_for_dataset,
    mask_bank_account_number,
    sanitize_sensitive_text,
)
from ledgerai_role1.governance.split import verify_split_integrity
from ledgerai_role1.ontology.fields import DocumentType

MANIFEST_PATH = Path("data/manifests/nova_dataset_manifest.json")


def test_manifest_loads_and_passes_governance() -> None:
    assert MANIFEST_PATH.exists(), "Manifest file must exist"
    manifest = DatasetManifest.load_from_file(MANIFEST_PATH)
    assert manifest.dataset_name == "NOVA-Financial-Documents-Synthetic"
    assert manifest.version == "1.0.0"
    assert "Apache-2.0" in manifest.license
    assert len(manifest.samples) >= 10


def test_split_integrity_strictly_disjoint() -> None:
    manifest = DatasetManifest.load_from_file(MANIFEST_PATH)
    counts = verify_split_integrity(manifest.samples)
    assert counts["train"] >= 5
    assert counts["val"] >= 2
    assert counts["test"] >= 5

    # Verify all document types are covered
    doc_types = {s.document_type for s in manifest.samples}
    assert DocumentType.SUPPLIER_INVOICE in doc_types
    assert DocumentType.CUSTOMER_INVOICE in doc_types
    assert DocumentType.RECEIPT in doc_types
    assert DocumentType.BANK_STATEMENT in doc_types
    assert DocumentType.PURCHASE_ORDER in doc_types


def test_redaction_and_masking() -> None:
    # Test bank account masking
    assert mask_bank_account_number("1234567890") == "****7890"
    assert mask_bank_account_number("987654321") == "****4321"
    assert mask_bank_account_number("123") == "****"

    # Test text sanitization
    raw_text = "Account: 1234567890, SSN: 000-12-3456, Card: 4111 1111 1111 1111"
    clean = sanitize_sensitive_text(raw_text)
    assert "4111 1111" not in clean
    assert "000-12-3456" not in clean
    assert "****7890" in clean


def test_assert_safe_for_dataset_rejects_credentials() -> None:
    with pytest.raises(ValueError, match="Sensitive credential"):
        assert_safe_for_dataset("My secret password is 123", "notes")

    with pytest.raises(ValueError, match="Unmasked payment card"):
        assert_safe_for_dataset("Card 4111-2222-3333-4444 used", "description")


def test_manifest_rejects_leaking_splits() -> None:
    manifest = DatasetManifest.load_from_file(MANIFEST_PATH)
    # sample 0 is in train; putting duplicate supplier in test violates disjointness
    leaking_sample = manifest.samples[0].model_copy(update={"split": "test"})
    corrupted_samples = list(manifest.samples) + [leaking_sample]

    with pytest.raises(ValueError, match="Supplier leak|Duplicate sample_id"):
        DatasetManifest(
            dataset_name=manifest.dataset_name,
            version=manifest.version,
            license=manifest.license,
            redaction_policy=manifest.redaction_policy,
            provenance_statement=manifest.provenance_statement,
            samples=corrupted_samples,
        )
