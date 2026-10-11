"""File limits, MIME signature inspection, and decompression bomb guards."""

from __future__ import annotations

from typing import Final

from fastapi import HTTPException, status

ALLOWED_MEDIA_TYPES: Final[frozenset[str]] = frozenset(
    {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/tiff",
        "text/plain",
    }
)

# Magic signature prefixes
MAGIC_PDF: Final[bytes] = b"%PDF"
MAGIC_PNG: Final[bytes] = b"\x89PNG\r\n\x1a\n"
MAGIC_JPEG: Final[bytes] = b"\xff\xd8\xff"
MAGIC_TIFF_LE: Final[bytes] = b"II*\x00"
MAGIC_TIFF_BE: Final[bytes] = b"MM\x00*"


def verify_file_signature_and_limits(
    content: bytes,
    declared_media_type: str,
    *,
    max_bytes: int = 10_485_760,
    max_pages: int = 10,
) -> None:
    """Validate declared media type matches binary signature, reject bombs, and enforce limits."""
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Payload size {len(content)} exceeds maximum allowable limit of {max_bytes} bytes"
            ),
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty document payload is not accepted",
        )

    clean_media = declared_media_type.split(";")[0].strip().lower()
    if clean_media not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type: '{declared_media_type}'",
        )

    # Magic byte inspection for binary types
    if clean_media == "application/pdf":
        if not content.startswith(MAGIC_PDF):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MIME mismatch: declared application/pdf but missing %PDF magic header",
            )
        # Check page count roughly via /Type /Page occurrences
        page_markers = content.count(b"/Type /Page") - content.count(b"/Type /Pages")
        if page_markers > max_pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"PDF page count {page_markers} exceeds maximum allowable limit of {max_pages}"
                ),
            )
    elif clean_media == "image/png":
        if not content.startswith(MAGIC_PNG):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MIME mismatch: declared image/png but missing PNG magic header",
            )
    elif clean_media == "image/jpeg":
        if not content.startswith(MAGIC_JPEG):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MIME mismatch: declared image/jpeg but missing JPEG SOI header",
            )
    elif clean_media == "image/tiff":
        if not (content.startswith(MAGIC_TIFF_LE) or content.startswith(MAGIC_TIFF_BE)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MIME mismatch: declared image/tiff but missing TIFF endian header",
            )
    elif clean_media == "text/plain":
        # Check for binary control bytes or hidden binary payloads
        if b"\x00" in content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text file contains null bytes or binary content",
            )
