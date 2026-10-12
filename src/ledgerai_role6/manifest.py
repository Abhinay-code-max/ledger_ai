"""Manifest loader and cryptographic integrity verifier."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ledgerai_contracts.v1.model_runtime import ModelManifest


class ManifestValidationError(RuntimeError):
    """Manifest verification error."""


def load_and_verify_manifest(
    manifest_path: Path,
    artifacts_dir: Path | None = None,
    *,
    verify_files_exist: bool = False,
) -> ModelManifest:
    """Load and validate a model manifest, verifying artifact SHA-256 hashes when configured."""
    if not manifest_path.exists():
        raise ManifestValidationError(f"Manifest file not found: {manifest_path}")

    try:
        raw_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ManifestValidationError(f"Malformed manifest JSON: {exc}") from exc

    try:
        manifest = ModelManifest.model_validate(raw_data)
    except Exception as exc:
        raise ManifestValidationError(f"Manifest schema validation failed: {exc}") from exc

    if verify_files_exist and artifacts_dir is not None:
        if not artifacts_dir.exists():
            raise ManifestValidationError(f"Artifacts directory not found: {artifacts_dir}")

        for relative_path, expected_hash in manifest.artifact_hashes.items():
            file_path = artifacts_dir / relative_path
            if not file_path.is_file():
                raise ManifestValidationError(f"Artifact file missing: {relative_path}")

            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            actual_hash = hasher.hexdigest().lower()
            if actual_hash != expected_hash.lower():
                raise ManifestValidationError(
                    f"Artifact hash mismatch for {relative_path}: "
                    f"expected {expected_hash}, got {actual_hash}"
                )

    return manifest
