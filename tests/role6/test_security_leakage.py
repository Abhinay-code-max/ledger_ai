"""Security tests verifying no token, prompt, document or secret leakage in logs or responses."""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from ledgerai_role6.app import create_role6_app
from ledgerai_role6.config import Role6Settings
from ledgerai_role6.observability import log_inference_event

SECRET_VALUE = "a" * 32
SECRET = SecretStr(SECRET_VALUE)


def test_no_token_or_prompt_leakage_in_telemetry(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="ledgerai_role6")

    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.supersecret"
    prompt = "This is a sensitive customer invoice prompt with SSN and banking"

    log_inference_event(
        event_type="test_event",
        operation_id=uuid4(),
        correlation_id=uuid4(),
        tenant_id=uuid4(),
        model_name="docintel-foundation-vlm",
        backend_type="DETERMINISTIC",
        extra={
            "token": token,
            "prompt": prompt,
            "document_text": prompt,
            "safe_tag": "public-metric",
        },
    )

    logged = caplog.text
    assert "public-metric" in logged
    assert token not in logged
    assert prompt not in logged


def test_error_response_neutral_and_does_not_leak_internals() -> None:
    settings = Role6Settings(
        environment="test",
        service_token_secret=SECRET,
        service_audience="ledgerai-role6",
    )
    app = create_role6_app(settings)
    client = TestClient(app)

    # Malformed json request without headers
    resp = client.post("/v1/models/infer", content=b"malformed")
    assert resp.status_code == 401
    assert "password" not in resp.text.lower()
    assert "traceback" not in resp.text.lower()
    assert "secret" not in resp.text.lower()


def test_outbound_network_disabled_by_default() -> None:
    settings = Role6Settings(environment="test")
    assert settings.allow_outbound_network is False

    with pytest.raises(ValueError, match="Outbound network access must remain disabled"):
        Role6Settings(
            environment="production",
            service_token_secret=SECRET,
            allow_outbound_network=True,
        )
