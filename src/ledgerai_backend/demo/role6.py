"""Role 6 application factory delegating directly to the real Role 6 local model gateway."""

from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import SecretStr

from ledgerai_role6.app import create_role6_app
from ledgerai_role6.config import Role6Settings


def create_demo_role6_app() -> FastAPI:
    """Delegate to the real Role 6 local model gateway runtime."""
    secret = os.environ.get(
        "LEDGERAI_ROLE6_SERVICE_TOKEN_SECRET",
        os.environ.get(
            "LEDGERAI_SERVICE_TOKEN_SECRET", "local-service-token-secret-32-chars-minimum"
        ),
    )
    settings = Role6Settings(
        environment="development",
        service_token_secret=SecretStr(secret),
        service_audience="ledgerai-role6",
        active_backend="deterministic",
        max_request_bytes=1_048_576,
    )
    return create_role6_app(settings)


app = create_demo_role6_app()
