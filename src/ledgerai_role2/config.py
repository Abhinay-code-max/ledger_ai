"""Configuration settings for Role 2 Accounting Core."""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Role2Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LEDGERAI_ROLE2_",
        extra="ignore",
    )

    service_name: str = "ledgerai-role2"
    service_version: str = "1.0.0"
    environment: str = "production"

    service_token_secret: SecretStr = SecretStr("x" * 32)
    service_token_audience: str = "ledgerai-role2"
    service_token_issuer: str = "ledgerai-backend"
    allowed_clock_skew_seconds: int = 5

    database_url: SecretStr | None = None
    runtime_dsn: SecretStr | None = None
    migration_dsn: SecretStr | None = None

    max_request_bytes: int = 1_048_576
    concurrency_limit: int = 100
