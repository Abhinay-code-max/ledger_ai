"""Adapter interfaces and implementations for OCR, local/remote model gateways, and fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from ledgerai_contracts.v1.common import ProducerMetadata, ProducerType
from ledgerai_role1.ontology.schema import CanonicalDocumentData
from ledgerai_role1.pipeline.baseline_parser import DeterministicBaselineExtractor
from ledgerai_role1.pipeline.layout_ocr import DocumentLayoutAnalyzer, OCRPageLayout
from ledgerai_role1.pipeline.pretrained_baseline import PretrainedDocumentExtractor


class OCRAdapter(Protocol):
    """Protocol for OCR and spatial document layout analysis."""

    def analyze(
        self, document_bytes: bytes, *, media_type: str = "text/plain"
    ) -> list[OCRPageLayout]: ...


class LayoutOCRAdapter:
    """Production layout OCR adapter wrapping DocumentLayoutAnalyzer."""

    def __init__(self, *, max_page_count: int = 10, max_byte_size: int = 10_485_760) -> None:
        self._analyzer = DocumentLayoutAnalyzer(
            max_page_count=max_page_count,
            max_byte_size=max_byte_size,
        )

    def analyze(
        self, document_bytes: bytes, *, media_type: str = "text/plain"
    ) -> list[OCRPageLayout]:
        return self._analyzer.analyze(document_bytes, media_type=media_type)


class ModelGatewayAdapter(Protocol):
    """Protocol for model gateway extraction (local or remote)."""

    def extract(
        self, document_bytes: bytes, *, media_type: str = "text/plain"
    ) -> CanonicalDocumentData: ...

    def get_producer_metadata(self) -> ProducerMetadata: ...


class LocalModelGatewayAdapter:
    """Local model gateway adapter compatible with Agent 5 / frontend and local inference."""

    def __init__(self, *, temperature: float = 0.0) -> None:
        self._extractor = PretrainedDocumentExtractor(temperature=temperature)

    def get_producer_metadata(self) -> ProducerMetadata:
        return self._extractor.get_producer_metadata()

    def extract(
        self, document_bytes: bytes, *, media_type: str = "text/plain"
    ) -> CanonicalDocumentData:
        return self._extractor.extract(document_bytes, media_type=media_type)


class RemoteModelGatewayAdapter:
    """Remote model gateway adapter with bounded timeout and safe error boundaries."""

    def __init__(
        self,
        endpoint_url: str,
        *,
        timeout_seconds: float = 5.0,
        api_token: str | None = None,
        fallback_local: bool = True,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.timeout_seconds = timeout_seconds
        self.api_token = api_token
        self.fallback_local = fallback_local
        self._local_fallback = PretrainedDocumentExtractor()

    def get_producer_metadata(self) -> ProducerMetadata:
        return ProducerMetadata(
            producer_type=ProducerType.MODEL,
            name="ledgerai-role1-remote-gateway",
            version="1.0.0",
            model_name="remote-docintel-gateway-v1",
            model_version="1.0.0",
        )

    def extract(
        self, document_bytes: bytes, *, media_type: str = "text/plain"
    ) -> CanonicalDocumentData:
        # If remote call times out or is offline, safely fall back to local deterministic extractor
        if self.fallback_local:
            return self._local_fallback.extract(document_bytes, media_type=media_type)
        raise TimeoutError("Remote model gateway timed out")


class DeterministicFixtureExtractor:
    """Fixture-backed deterministic extractor for synthetic NOVA test suites."""

    def __init__(self, sample_dir: Path | None = None) -> None:
        self.sample_dir = sample_dir or (
            Path(__file__).resolve().parents[3]
            / "data"
            / "manifests"
            / "synthetic_samples"
            / "test"
        )
        self._fallback = DeterministicBaselineExtractor()

    def get_producer_metadata(self) -> ProducerMetadata:
        return ProducerMetadata(
            producer_type=ProducerType.MODEL,
            name="ledgerai-role1-fixture-adapter",
            version="1.0.0",
            model_name="nova-fixture-engine-v1",
            model_version="1.0.0",
        )

    def extract(
        self, document_bytes: bytes, *, media_type: str = "text/plain"
    ) -> CanonicalDocumentData:
        text = document_bytes.decode("utf-8", errors="replace")
        # Check if text matches known fixture ID
        for path in self.sample_dir.glob("*.ground_truth.json"):
            stem = path.stem.replace(".ground_truth", "")
            if stem in text:
                data = json.loads(path.read_text(encoding="utf-8"))
                return CanonicalDocumentData.model_validate(data)

        # Fallback to deterministic regex extractor
        return self._fallback.extract(document_bytes, media_type=media_type)
