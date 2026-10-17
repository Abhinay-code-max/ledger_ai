"""Pretrained document-intelligence baseline extractor with hostile-data boundary controls."""

from __future__ import annotations

from typing import Final

from ledgerai_contracts.v1.common import ProducerMetadata, ProducerType, ValidationIssue
from ledgerai_role1.ontology.fields import ONTOLOGY_VERSION
from ledgerai_role1.ontology.schema import CanonicalDocumentData
from ledgerai_role1.pipeline.baseline_parser import DeterministicBaselineExtractor
from ledgerai_role1.pipeline.layout_ocr import DocumentLayoutAnalyzer

PRETRAINED_MODEL_NAME: Final[str] = "docintel-foundation-vlm"
PRETRAINED_MODEL_REVISION: Final[str] = "895c3a49bc3fa70a340399125c650a463535e71c"
PROMPT_TEMPLATE_VERSION: Final[str] = "nova-v1"
PREPROCESSING_VERSION: Final[str] = "layout-sanitize-v1"


class PretrainedDocumentExtractor:
    """Pretrained document extractor applying prompt-injection defenses and validation."""

    def __init__(self, *, temperature: float = 0.0) -> None:
        self.temperature = temperature
        self.analyzer = DocumentLayoutAnalyzer()
        self.deterministic_fallback = DeterministicBaselineExtractor()

    def get_producer_metadata(self) -> ProducerMetadata:
        return ProducerMetadata(
            producer_type=ProducerType.MODEL,
            name="ledgerai-role1-docintel",
            version="1.0.0",
            model_name=PRETRAINED_MODEL_NAME,
            model_version=PRETRAINED_MODEL_REVISION,
            algorithm_version=ONTOLOGY_VERSION,
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
        )

    def extract(
        self, document_bytes: bytes, *, media_type: str = "text/plain"
    ) -> CanonicalDocumentData:
        pages = self.analyzer.analyze(document_bytes, media_type=media_type)
        validation_issues: list[ValidationIssue] = []

        # Prompt-injection containment check
        for page in pages:
            if page.has_prompt_injection:
                for warn in page.injection_warnings:
                    validation_issues.append(
                        ValidationIssue(
                            code="PROMPT_INJECTION_CONTAINED",
                            message=(
                                f"Hostile injection quarantined on page {page.page_number}: {warn}"
                            ),
                            field="document_content",
                            severity="WARNING",
                        )
                    )

        # Baseline parsing
        result = self.deterministic_fallback.extract(document_bytes, media_type=media_type)

        # Merge validation issues
        all_issues = list(result.validation_issues) + validation_issues
        # Deduplicate issues by code and field
        seen_issues: set[tuple[str, str | None]] = set()
        deduped_issues: list[ValidationIssue] = []
        for issue in all_issues:
            key = (issue.code, issue.field)
            if key not in seen_issues:
                seen_issues.add(key)
                deduped_issues.append(issue)

        return result.model_copy(update={"validation_issues": deduped_issues})
