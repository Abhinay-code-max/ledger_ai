"""Role 1 application factory delegating directly to the real ledgerai_role1 service."""

from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import SecretStr

from ledgerai_role1.service.app import create_app
from ledgerai_role1.service.config import Role1Settings


def create_demo_role1_app() -> FastAPI:
    """Delegate to real Role 1 Document Intelligence service."""
    secret = os.environ.get(
        "LEDGERAI_ROLE1_SERVICE_TOKEN_SECRET",
        os.environ.get("LEDGERAI_SERVICE_TOKEN_SECRET", "synthetic-service-secret-for-nova-0001"),
    )
    audience = os.environ.get("LEDGERAI_ROLE1_AUDIENCE", "ledgerai-role1")
    settings = Role1Settings(
        environment=os.environ.get("LEDGERAI_ENVIRONMENT", "test"),
        service_token_secret=SecretStr(secret),
        audience=audience,
    )
    app = create_app(settings)

    # Configure real storage loader if object storage is configured
    endpoint = os.environ.get("LEDGERAI_STORAGE_ENDPOINT_URL")
    access_key = os.environ.get("LEDGERAI_STORAGE_ACCESS_KEY")
    secret_key = os.environ.get("LEDGERAI_STORAGE_SECRET_KEY")
    bucket = os.environ.get("LEDGERAI_STORAGE_BUCKET", "ledgerai-evidence")
    if endpoint and access_key and secret_key:
        try:
            import boto3  # type: ignore[import-untyped]

            s3 = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=os.environ.get("LEDGERAI_STORAGE_REGION", "us-east-1"),
            )

            def s3_loader(object_key: str) -> bytes:
                resp = s3.get_object(Bucket=bucket, Key=object_key)
                return bytes(resp["Body"].read())

            app.state.storage_loader = s3_loader
        except Exception:
            pass
    else:
        from pathlib import Path

        invoice_path = (
            Path(__file__).resolve().parents[3]
            / "demo"
            / "nova"
            / "documents"
            / "NOVA_SYNTHETIC_INVOICE_001.pdf"
        )
        if invoice_path.exists():
            pdf_bytes = invoice_path.read_bytes()
            app.state.storage_loader = lambda _: pdf_bytes

    return app


app = create_demo_role1_app()
