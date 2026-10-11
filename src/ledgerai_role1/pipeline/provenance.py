"""Provenance and bounding-box computation utilities."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from ledgerai_role1.ontology.schema import AnnotatedProvenance


def compute_evidence_hash(data: bytes | str) -> str:
    """Compute deterministic SHA-256 evidence hash for provenance audit trails."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def create_token_provenance(
    *,
    text: str,
    page_number: int = 1,
    x: Decimal = Decimal("10.0"),
    y: Decimal = Decimal("10.0"),
    width: Decimal = Decimal("100.0"),
    height: Decimal = Decimal("15.0"),
    confidence: Decimal = Decimal("0.95"),
    document_bytes: bytes | None = None,
) -> AnnotatedProvenance:
    """Create a standardized provenance record with bounding box and evidence hash."""
    evidence_hash = compute_evidence_hash(document_bytes or text.encode("utf-8"))
    return AnnotatedProvenance(
        page_number=page_number,
        x=x,
        y=y,
        width=width,
        height=height,
        text_snippet=text[:100],
        confidence=confidence,
        evidence_hash=evidence_hash,
    )
