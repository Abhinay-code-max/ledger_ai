"""Ontology definitions for Role 1."""

from ledgerai_role1.ontology.fields import (
    CRITICAL_FIELDS_BY_DOC_TYPE,
    ONTOLOGY_VERSION,
    CanonicalFieldName,
    DocumentType,
)
from ledgerai_role1.ontology.schema import (
    AnnotatedLineItem,
    AnnotatedProvenance,
    CanonicalDocumentData,
    to_contract_extraction,
)

__all__ = [
    "CRITICAL_FIELDS_BY_DOC_TYPE",
    "ONTOLOGY_VERSION",
    "AnnotatedLineItem",
    "AnnotatedProvenance",
    "CanonicalDocumentData",
    "CanonicalFieldName",
    "DocumentType",
    "to_contract_extraction",
]
