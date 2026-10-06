import pytest
from pydantic import SecretStr, ValidationError

from ledgerai_backend.core.config import Settings


def test_development_defaults_deny_cors_and_redact_secrets() -> None:
    settings = Settings(
        database_dsn=SecretStr("postgresql+psycopg://user:secret@db/ledgerai"),
    )
    assert settings.cors_origins == []
    assert settings.allowed_hosts == ["localhost", "127.0.0.1"]
    assert "secret" not in repr(settings)


def test_production_fails_closed_without_identity_or_database() -> None:
    with pytest.raises(ValidationError, match="production configuration missing"):
        Settings(environment="production")


def test_test_identity_can_never_activate_in_production() -> None:
    with pytest.raises(ValidationError, match="test identity cannot be enabled"):
        Settings(
            environment="production",
            database_dsn=SecretStr("postgresql+psycopg://runtime:redacted@db/ledgerai"),
            jwt_issuer="https://issuer.invalid/",
            jwt_audience="ledgerai-api",
            jwt_public_key=SecretStr("public-key"),
            enable_test_identity=True,
        )


def test_none_algorithm_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cannot contain 'none'"):
        Settings(jwt_algorithms=["none"])
