"""Generate or verify the deterministic Phase 1 OpenAPI document."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ledgerai_backend.core.config import Settings
from ledgerai_backend.main import create_app

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "shared" / "openapi" / "v1.json"


def rendered_openapi() -> str:
    settings = Settings(
        environment="test",
        allowed_hosts=["testserver"],
        service_version="1.3.0",
    )
    document = create_app(settings).openapi()
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = rendered_openapi()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            raise SystemExit("OpenAPI artifact is stale; run tools/generate_openapi.py")
        print("Checked deterministic OpenAPI artifact.")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
