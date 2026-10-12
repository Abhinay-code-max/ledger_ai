"""Normalize and compare safe NOVA machine-readable results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

VOLATILE_KEYS = frozenset(
    {"request_id", "correlation_id", "occurred_at", "created_at", "updated_at"}
)


def normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize(value[key]) for key in sorted(value) if key not in VOLATILE_KEYS}
    if isinstance(value, list):
        normalized = [normalize(item) for item in value]
        if all(not isinstance(item, (dict, list)) for item in normalized):
            return sorted(normalized, key=str)
        return normalized
    return value


def compare(left: Any, right: Any) -> bool:
    return bool(normalize(left) == normalize(right))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    args = parser.parse_args()
    left = json.loads(args.left.read_text(encoding="utf-8"))
    right = json.loads(args.right.read_text(encoding="utf-8"))
    if not compare(left, right):
        raise SystemExit("normalized NOVA results differ")
    print(json.dumps(normalize(left), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
