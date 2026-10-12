"""Resource bounds validation and untrusted input safety."""

from __future__ import annotations

import re

from fastapi import HTTPException, status

from ledgerai_contracts.v1.model_runtime import (
    InferenceInput,
    ManifestResourceLimits,
)

_SAFE_STORAGE_KEY_RE = re.compile(r"^[A-Za-z0-9/_.-]+$")


def validate_input_bounds(
    input_data: InferenceInput,
    limits: ManifestResourceLimits,
    *,
    allowlisted_storage_prefix: str = "ledgerai-evidence/",
) -> None:
    """Validate request size, page counts, pixels, and storage references."""
    # Validate text content
    if input_data.text_content is not None:
        raw_bytes = input_data.text_content.encode("utf-8")
        if len(raw_bytes) > limits.max_request_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"Request text size {len(raw_bytes)} bytes exceeds "
                    f"limit {limits.max_request_bytes}"
                ),
            )

        # Rough token approximation (1 token ~= 4 chars) to reject egregious prompts early
        approx_tokens = len(input_data.text_content) // 4
        if approx_tokens > limits.max_input_tokens:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Input approximate tokens {approx_tokens} exceeds "
                    f"maximum allowed {limits.max_input_tokens}"
                ),
            )

    # Validate page bounds
    if input_data.page_count is not None and input_data.page_count > limits.max_pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Page count {input_data.page_count} exceeds limit {limits.max_pages}",
        )

    # Validate image pixels
    if input_data.pixel_count is not None and input_data.pixel_count > limits.max_image_pixels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Image pixel count {input_data.pixel_count} exceeds "
                f"limit {limits.max_image_pixels}"
            ),
        )

    # Validate storage reference
    if input_data.storage_reference is not None:
        key = input_data.storage_reference
        if ".." in key or "\\" in key or key.startswith("/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path traversal in storage reference forbidden",
            )
        if not _SAFE_STORAGE_KEY_RE.match(key):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Storage reference contains forbidden characters",
            )
        if not key.startswith(allowlisted_storage_prefix):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Storage reference must start with prefix '{allowlisted_storage_prefix}'",
            )
