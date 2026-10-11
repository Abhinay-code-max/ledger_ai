"""Split generation and verification utilities ensuring zero train-test data leakage."""

from __future__ import annotations

from collections.abc import Sequence

from ledgerai_role1.governance.manifest import SampleManifestItem


def verify_split_integrity(samples: Sequence[SampleManifestItem]) -> dict[str, int]:
    """Verify that splits have no overlapping suppliers, templates, or hashes."""
    counts = {"train": 0, "val": 0, "test": 0}
    suppliers: dict[str, set[str]] = {"train": set(), "val": set(), "test": set()}
    templates: dict[str, set[str]] = {"train": set(), "val": set(), "test": set()}
    hashes: dict[str, set[str]] = {"train": set(), "val": set(), "test": set()}

    for item in samples:
        counts[item.split] += 1
        suppliers[item.split].add(item.supplier_id)
        templates[item.split].add(item.template_id)
        hashes[item.split].add(item.sha256_hash)

    # Cross-split checks
    assert not (suppliers["train"] & suppliers["test"]), (
        f"Supplier leak: {suppliers['train'] & suppliers['test']}"
    )
    assert not (suppliers["val"] & suppliers["test"]), (
        f"Supplier leak: {suppliers['val'] & suppliers['test']}"
    )
    assert not (templates["train"] & templates["test"]), (
        f"Template leak: {templates['train'] & templates['test']}"
    )
    assert not (templates["val"] & templates["test"]), (
        f"Template leak: {templates['val'] & templates['test']}"
    )
    assert not (hashes["train"] & hashes["test"]), "Hash leak between train and test"
    assert not (hashes["val"] & hashes["test"]), "Hash leak between val and test"

    return counts
