"""Typed, fail-closed application configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment configuration; secret fields stay redacted in representations."""

    model_config = SettingsConfigDict(
        env_prefix="LEDGERAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_dsn: SecretStr | None = None
    migration_dsn: SecretStr | None = None
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    cors_origins: list[str] = Field(default_factory=list)
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    jwks_url: str | None = None
    jwt_public_key: SecretStr | None = None
    enable_test_identity: bool = False
    log_level: str = "INFO"
    service_name: str = "ledgerai-backend"
    service_version: str = "1.2.0"
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    max_request_bytes: int = Field(default=1_048_576, ge=1_024, le=10_485_760)
    storage_endpoint_url: str | None = None
    storage_region: str = "us-east-1"
    storage_bucket: str = "ledgerai-evidence"
    storage_access_key: SecretStr | None = None
    storage_secret_key: SecretStr | None = Field(default=None, repr=False)
    storage_use_tls: bool = True
    storage_presign_seconds: int = Field(default=300, ge=60, le=900)
    storage_max_upload_bytes: int = Field(default=10_485_760, ge=1, le=52_428_800)
    scanner_adapter: Literal["deterministic", "clamav"] | None = None
    scanner_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    redis_url: SecretStr | None = None
    queue_default: str = "ledgerai.workflow"
    queue_max_attempts: int = Field(default=5, ge=1, le=20)
    csv_max_rows: int = Field(default=10_000, ge=1, le=100_000)
    csv_max_columns: int = Field(default=32, ge=1, le=128)
    csv_max_cell_chars: int = Field(default=4_096, ge=1, le=65_536)
    idempotency_ttl_seconds: int = Field(default=86_400, ge=300, le=2_592_000)

    @model_validator(mode="after")
    def validate_security(self) -> Self:
        if any(algorithm.lower() == "none" for algorithm in self.jwt_algorithms):
            raise ValueError("jwt_algorithms cannot contain 'none'")
        if not self.jwt_algorithms:
            raise ValueError("jwt_algorithms cannot be empty")
        if self.environment == "production":
            if self.enable_test_identity:
                raise ValueError("test identity cannot be enabled in production")
            missing = [
                name
                for name, value in (
                    ("database_dsn", self.database_dsn),
                    ("jwt_issuer", self.jwt_issuer),
                    ("jwt_audience", self.jwt_audience),
                )
                if not value
            ]
            if not (self.jwks_url or self.jwt_public_key):
                missing.append("jwks_url or jwt_public_key")
            for name, value in (
                ("storage_endpoint_url", self.storage_endpoint_url),
                ("storage_access_key", self.storage_access_key),
                ("storage_secret_key", self.storage_secret_key),
                ("scanner_adapter", self.scanner_adapter),
                ("redis_url", self.redis_url),
            ):
                if not value:
                    missing.append(name)
            if self.scanner_adapter == "deterministic":
                raise ValueError("deterministic scanner cannot be enabled in production")
            if missing:
                raise ValueError(f"production configuration missing: {', '.join(missing)}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
