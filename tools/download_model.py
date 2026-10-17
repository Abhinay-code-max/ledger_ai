"""Downloader and cryptographic verification tool for Qwen2-VL-2B-Instruct."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from huggingface_hub import snapshot_download  # type: ignore[import-not-found]

REPO_ID = "Qwen/Qwen2-VL-2B-Instruct"
REVISION = "895c3a49bc3fa70a340399125c650a463535e71c"
TARGET_DIR = Path("models/artifacts/qwen2-vl-2b-instruct")

EXPECTED_SHA256 = {
    "config.json": "422adefa19e62dd175961cec85bc0400344fe5bf9b22bd1182e05aaae78556e0",
    "tokenizer.json": "cb63a0a23eef3d5b01063a9880a1925a65aaf4d1591d519910ee3527852950a0",
    "model.safetensors.index.json": (
        "260ab9fa1418d6d6ab79daa1d9da2c47264f3b72edb4630fc799077ac67d27c6"
    ),
    "model-00001-of-00002.safetensors": (
        "994ac2b03f97de8bc647d0fe5eba2e4b632b3e28dc03574c29bdfc36cf47e1b9"
    ),
    "model-00002-of-00002.safetensors": (
        "92540d8353c8d226a589a3b179bdb33851c970ee2cc2ac7ba035f79425e7b833"
    ),
}


def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    print(f"Downloading {REPO_ID} (revision: {REVISION}) to {TARGET_DIR}...")
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=REPO_ID,
        revision=REVISION,
        local_dir=str(TARGET_DIR),
        local_dir_use_symlinks=False,
    )
    print("Download completed. Verifying cryptographic checksums...")

    all_matched = True
    for filename, expected_hash in EXPECTED_SHA256.items():
        file_path = TARGET_DIR / filename
        if not file_path.exists():
            print(f"[MISSING] {filename} does not exist!")
            all_matched = False
            continue

        actual_hash = compute_sha256(file_path)
        if actual_hash.lower() == expected_hash.lower():
            print(f"[VERIFIED] {filename} -> {actual_hash[:16]}... OK")
        else:
            print(f"[MISMATCH] {filename} -> Expected {expected_hash}, got {actual_hash}")
            all_matched = False

    if all_matched:
        print("\nAll artifact checksums VERIFIED successfully!")
        print("Ready for GPU neural inference.")
    else:
        print("\nVerification FAILED. Some files are missing or corrupted.")
        sys.exit(1)


if __name__ == "__main__":
    main()
