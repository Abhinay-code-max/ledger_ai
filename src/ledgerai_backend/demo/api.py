"""Non-production NOVA API process used by the Compose stub profile."""

from __future__ import annotations

import os

from ledgerai_backend.demo.runner import _identity, _settings
from ledgerai_backend.main import create_app


def _required_url(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


app = create_app(
    _settings(
        _required_url("LEDGERAI_DEMO_ROLE1_URL"),
        _required_url("LEDGERAI_DEMO_ROLE2_URL"),
        _required_url("LEDGERAI_DEMO_ROLE3_URL"),
        _required_url("LEDGERAI_DEMO_ROLE6_URL"),
    ),
    identity_provider=_identity(),
)
