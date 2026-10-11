"""Generate or verify the deterministic Role 2 OpenAPI specification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ledgerai_role2.api.app import create_role2_app
from ledgerai_role2.config import Role2Settings

OUTPUT = ROOT / "shared" / "openapi" / "role2_v1.json"


def rendered_openapi() -> str:
    settings = Role2Settings(
        environment="test",
        service_version="2.0.0",
    )
    document = create_role2_app(settings).openapi()
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = rendered_openapi()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            raise SystemExit("Role 2 OpenAPI artifact is stale; run tools/generate_role2_openapi.py")
        print("Checked deterministic Role 2 OpenAPI artifact.")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
