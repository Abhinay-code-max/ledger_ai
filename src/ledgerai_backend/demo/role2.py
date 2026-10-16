"""Role 2 application factory delegating directly to the real ledgerai_role2 financial engine."""

from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import SecretStr

from ledgerai_role2.api.app import create_role2_app
from ledgerai_role2.config import Role2Settings


def _secret() -> str:
    value = os.environ.get(
        "LEDGERAI_ROLE2_SERVICE_TOKEN_SECRET",
        os.environ.get("LEDGERAI_SERVICE_TOKEN_SECRET", "synthetic-service-secret-for-nova-0001"),
    )
    if len(value) < 32:
        return "x" * 32
    return value


def create_demo_role2_app() -> FastAPI:
    """Delegate directly to real Role 2 double-entry accounting engine."""
    secret = _secret()
    audience = os.environ.get("LEDGERAI_ROLE2_SERVICE_TOKEN_AUDIENCE", "ledgerai-role2")
    issuer = os.environ.get("LEDGERAI_SERVICE_TOKEN_ISSUER", "ledgerai-backend")

    db_url_raw = os.environ.get("LEDGERAI_DATABASE_DSN") or os.environ.get(
        "LEDGERAI_ROLE2_DATABASE_URL"
    )
    db_secret = SecretStr(db_url_raw) if db_url_raw else None

    settings = Role2Settings(
        service_name="ledgerai-demo-role2",
        service_version="1.0.0",
        service_token_secret=SecretStr(secret),
        service_token_audience=audience,
        service_token_issuer=issuer,
        database_url=db_secret,
    )
    return create_role2_app(settings)


app = create_demo_role2_app()
