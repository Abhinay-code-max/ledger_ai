"""Layout-aware OCR and tokenization with adversarial prompt-injection defenses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

# Adversarial prompt-injection signatures inside document text
PROMPT_INJECTION_SIGNATURES: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(?i)\bignore (?:all )?(?:previous|prior) instructions\b"),
    re.compile(
        r"(?i)\byou are now (?:in )?(?:a |an )?(?:debug|admin|root|jailbroken|unrestricted) mode\b"
    ),
    re.compile(r"(?i)\bdisregard (?:all )?system (?:rules|prompts|guidelines)\b"),
    re.compile(r"(?i)\bdo not validate (?:totals|amounts|fields)\b"),
    re.compile(r"(?i)\bset approval_disposition to not_required\b"),
    re.compile(r"(?i)\bexecute command:\s*"),
    re.compile(r"(?i)\bsystem prompt override:\s*"),
)


@dataclass(frozen=True, slots=True)
class OCRToken:
    """Individual layout token with bounding-box coordinates."""

    text: str
    page: int
    x: Decimal
    y: Decimal
    width: Decimal
    height: Decimal
    confidence: Decimal


@dataclass(frozen=True, slots=True)
class OCRPageLayout:
    """Page layout containing text tokens and adversarial security alerts."""

    page_number: int
    raw_text: str
    tokens: tuple[OCRToken, ...]
    has_prompt_injection: bool
    injection_warnings: tuple[str, ...]


class DocumentLayoutAnalyzer:
    """Extracts spatial layout tokens and validates adversarial safety."""

    def __init__(self, *, max_page_count: int = 10, max_byte_size: int = 10_485_760) -> None:
        self.max_page_count = max_page_count
        self.max_byte_size = max_byte_size

    def analyze(self, document_bytes: bytes, media_type: str = "text/plain") -> list[OCRPageLayout]:
        if len(document_bytes) > self.max_byte_size:
            raise ValueError(
                f"Document size {len(document_bytes)} exceeds maximum "
                f"limit of {self.max_byte_size} bytes"
            )

        # Decode document text safely
        try:
            text = document_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            raise ValueError("Malformed document content encoding") from e

        # Handle multipage split (e.g. form-feed or page breaks)
        raw_pages = text.split("\x0c") if "\x0c" in text else [text]
        if len(raw_pages) > self.max_page_count:
            raise ValueError(
                f"Page count {len(raw_pages)} exceeds maximum "
                f"allowable limit of {self.max_page_count}"
            )

        pages: list[OCRPageLayout] = []
        for page_idx, page_text in enumerate(raw_pages, start=1):
            injection_warnings: list[str] = []
            has_injection = False

            # Check prompt injection patterns
            for pattern in PROMPT_INJECTION_SIGNATURES:
                if pattern.search(page_text):
                    has_injection = True
                    injection_warnings.append(
                        f"Detected hostile instruction pattern: {pattern.pattern}"
                    )

            # Tokenize into layout lines
            tokens: list[OCRToken] = []
            lines = page_text.splitlines()
            current_y = Decimal("50.0")

            for line in lines:
                stripped = line.strip()
                if stripped:
                    # Estimate bounding box coordinates
                    width = Decimal(str(max(10, len(stripped) * 7)))
                    height = Decimal("15.0")
                    tokens.append(
                        OCRToken(
                            text=stripped,
                            page=page_idx,
                            x=Decimal("20.0"),
                            y=current_y,
                            width=width,
                            height=height,
                            confidence=Decimal("0.98"),
                        )
                    )
                current_y += Decimal("20.0")

            pages.append(
                OCRPageLayout(
                    page_number=page_idx,
                    raw_text=page_text,
                    tokens=tuple(tokens),
                    has_prompt_injection=has_injection,
                    injection_warnings=tuple(injection_warnings),
                )
            )

        return pages
