from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import SecretStr

from ledgerai_backend.core.config import Settings
from ledgerai_backend.demo.reset import NOVA_TENANT_ID, DemoResetError, _require_safe_reset
from ledgerai_backend.demo.runner import DemoFailure, _safe_local_url, _settings


def test_demo_reset_refuses_production() -> None:
    settings = Settings(
        environment="production",
        database_dsn=SecretStr("postgresql+psycopg://runtime.invalid/db"),
        migration_dsn=SecretStr("postgresql+psycopg://migrator.invalid/db"),
        jwt_issuer="https://identity.invalid/",
        jwt_audience="ledgerai",
        jwt_public_key=SecretStr("public-key"),
        storage_endpoint_url="https://storage.invalid",
        storage_access_key=SecretStr("access"),
        storage_secret_key=SecretStr("secret"),
        scanner_adapter="clamav",
        redis_url=SecretStr("redis://redis.invalid/0"),
        role1_base_url="https://role1.invalid",
        role2_base_url="https://role2.invalid",
        role3_base_url="https://role3.invalid",
        role6_base_url="https://role6.invalid",
        service_token_secret=SecretStr("x" * 32),
    )
    with pytest.raises(DemoResetError, match="prohibited"):
        _require_safe_reset(settings, confirmed=True, tenant_id=NOVA_TENANT_ID)


def test_demo_reset_requires_confirmation() -> None:
    settings = Settings(environment="test", migration_dsn=SecretStr("postgresql://invalid"))
    with pytest.raises(DemoResetError, match="confirmation"):
        _require_safe_reset(settings, confirmed=False, tenant_id=NOVA_TENANT_ID)


def test_demo_reset_rejects_wrong_tenant() -> None:
    settings = Settings(environment="test", migration_dsn=SecretStr("postgresql://invalid"))
    with pytest.raises(DemoResetError, match="arbitrary tenant"):
        _require_safe_reset(settings, confirmed=True, tenant_id=uuid4())


def test_demo_endpoint_allowlist_rejects_remote_and_credential_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REMOTE_DEMO_URL", "https://example.invalid/path")
    with pytest.raises(DemoFailure, match="allowlisted"):
        _safe_local_url("REMOTE_DEMO_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("REMOTE_DEMO_URL", "http://user:password@127.0.0.1:1")
    with pytest.raises(DemoFailure, match="prohibited"):
        _safe_local_url("REMOTE_DEMO_URL", "http://127.0.0.1:1")


def test_demo_requires_explicit_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERAI_ENVIRONMENT", "test")
    monkeypatch.delenv("LEDGERAI_DEMO_ENABLED", raising=False)
    with pytest.raises(DemoFailure, match="DEMO_ENABLED"):
        _settings()


def test_settings_refuses_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERAI_ENVIRONMENT", "production")
    with pytest.raises(DemoFailure, match="prohibited in production"):
        _settings()


def test_settings_requires_reset_confirm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERAI_ENVIRONMENT", "test")
    monkeypatch.setenv("LEDGERAI_DEMO_ENABLED", "true")
    monkeypatch.delenv("LEDGERAI_DEMO_RESET_CONFIRM", raising=False)
    with pytest.raises(DemoFailure, match="RESET_NOVA_ONLY"):
        _settings()


def test_settings_configures_role_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERAI_ENVIRONMENT", "test")
    monkeypatch.setenv("LEDGERAI_DEMO_ENABLED", "true")
    monkeypatch.setenv("LEDGERAI_DEMO_RESET_CONFIRM", "RESET_NOVA_ONLY")
    monkeypatch.setenv("LEDGERAI_SERVICE_TOKEN_SECRET", "s" * 32)
    monkeypatch.setenv("LEDGERAI_DATABASE_DSN", "postgresql://db")
    monkeypatch.setenv("LEDGERAI_MIGRATION_DSN", "postgresql://db")
    monkeypatch.setenv("LEDGERAI_STORAGE_ENDPOINT_URL", "http://127.0.0.1:9000")
    monkeypatch.setenv("LEDGERAI_STORAGE_ACCESS_KEY", "access")
    monkeypatch.setenv("LEDGERAI_STORAGE_SECRET_KEY", "secret")
    monkeypatch.setenv("LEDGERAI_REDIS_URL", "redis://127.0.0.1:6379/0")
    settings = _settings("http://127.0.0.1:8101", "http://127.0.0.1:8102", "http://127.0.0.1:8103")
    assert settings.role1_base_url == "http://127.0.0.1:8101"
    assert settings.role2_base_url == "http://127.0.0.1:8102"
    assert settings.role3_base_url == "http://127.0.0.1:8103"
