"""Dataset manifest definition and strict governance checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ledgerai_role1.ontology.fields import DocumentType


class SampleManifestItem(BaseModel):
    """Manifest item representing a single document sample with immutable hash and metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sample_id: str = Field(min_length=1)
    document_type: DocumentType
    split: Literal["train", "val", "test"]
    template_id: str = Field(min_length=1)
    supplier_id: str = Field(min_length=1)
    sha256_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: str = Field(pattern=r"^[\w.+-]+/[\w.+-]+$")
    byte_size: int = Field(ge=1)
    document_path: str = Field(min_length=1)
    ground_truth_path: str = Field(min_length=1)


class DatasetManifest(BaseModel):
    """Dataset manifest with license, provenance, and split isolation invariants."""

    model_config = ConfigDict(extra="forbid")

    dataset_name: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    license: str = Field(min_length=1)
    redaction_policy: str = Field(min_length=1)
    provenance_statement: str = Field(min_length=1)
    samples: list[SampleManifestItem] = Field(min_length=1)

    @field_validator("license")
    @classmethod
    def validate_allowed_licenses(cls, v: str) -> str:
        allowed = {"Apache-2.0", "CC-BY-4.0", "CC0-1.0", "MIT"}
        if not any(lic in v for lic in allowed):
            raise ValueError(
                f"License '{v}' not among authorized synthetic/open licenses: {allowed}"
            )
        return v

    @model_validator(mode="after")
    def validate_split_isolation(self) -> DatasetManifest:
        """Enforce zero-leakage invariant across suppliers, templates, and hashes."""
        train_suppliers: set[str] = set()
        val_suppliers: set[str] = set()
        test_suppliers: set[str] = set()

        train_templates: set[str] = set()
        val_templates: set[str] = set()
        test_templates: set[str] = set()

        train_hashes: set[str] = set()
        val_hashes: set[str] = set()
        test_hashes: set[str] = set()

        sample_ids: set[str] = set()

        for s in self.samples:
            if s.sample_id in sample_ids:
                raise ValueError(f"Duplicate sample_id found: {s.sample_id}")
            sample_ids.add(s.sample_id)

            if s.split == "train":
                train_suppliers.add(s.supplier_id)
                train_templates.add(s.template_id)
                train_hashes.add(s.sha256_hash)
            elif s.split == "val":
                val_suppliers.add(s.supplier_id)
                val_templates.add(s.template_id)
                val_hashes.add(s.sha256_hash)
            elif s.split == "test":
                test_suppliers.add(s.supplier_id)
                test_templates.add(s.template_id)
                test_hashes.add(s.sha256_hash)

        # Check disjoint supplier sets
        if train_suppliers.intersection(test_suppliers):
            leaked = train_suppliers.intersection(test_suppliers)
            raise ValueError(f"Supplier leak between train and test splits: {leaked}")
        if val_suppliers.intersection(test_suppliers):
            leaked = val_suppliers.intersection(test_suppliers)
            raise ValueError(f"Supplier leak between val and test splits: {leaked}")

        # Check disjoint templates
        if train_templates.intersection(test_templates):
            leaked = train_templates.intersection(test_templates)
            raise ValueError(f"Template leak between train and test splits: {leaked}")
        if val_templates.intersection(test_templates):
            leaked = val_templates.intersection(test_templates)
            raise ValueError(f"Template leak between val and test splits: {leaked}")

        # Check disjoint document hashes
        if train_hashes.intersection(test_hashes):
            raise ValueError("Document hash leak between train and test splits")
        if val_hashes.intersection(test_hashes):
            raise ValueError("Document hash leak between val and test splits")

        return self

    def save_to_file(self, path: Path) -> None:
        path.write_text(json.dumps(self.model_dump(mode="json"), indent=2), encoding="utf-8")

    @classmethod
    def load_from_file(cls, path: Path) -> DatasetManifest:
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))
