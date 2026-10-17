"""Strict, fail-closed configuration for Role 6 Model Gateway."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Role6Settings(BaseSettings):
    """Configuration for Role 6 Local Model Runtime."""

    model_config = SettingsConfigDict(
        env_prefix="LEDGERAI_ROLE6_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8006, ge=1, le=65535)
    service_name: str = "ledgerai-role6-model-gateway"
    service_version: str = "1.0.0"
    service_audience: str = "ledgerai-role6"
    allowed_issuers: list[str] = Field(
        default_factory=lambda: ["ledgerai-backend", "role4-orchestration", "ledgerai-role1"]
    )
    allowed_calling_services: list[str] = Field(
        default_factory=lambda: [
            "ledgerai-backend",
            "role4-backend",
            "ledgerai-role1",
            "role1-document-intelligence",
        ]
    )
    service_token_secret: SecretStr | None = Field(default=None, repr=False)
    jwt_algorithms: list[str] = Field(default_factory=lambda: ["HS256"])

    # Model and Backend Configuration
    active_backend: Literal["deterministic", "real_onnx", "real_vlm", "mock"] = "deterministic"
    model_manifest_path: str = Field(default="models/manifests/ledgerai_docintel_v1.manifest.json")
    model_artifacts_dir: str = Field(default="models/artifacts")
    allow_outbound_network: bool = False

    # Hard resource bounds
    max_request_bytes: int = Field(default=10_485_760, ge=1024, le=52_428_800)
    max_pages: int = Field(default=20, ge=1, le=100)
    max_image_pixels: int = Field(default=16_000_000, ge=10_000, le=100_000_000)
    max_input_tokens: int = Field(default=8_192, ge=16, le=131_072)
    max_output_tokens: int = Field(default=4_096, ge=16, le=32_768)
    wall_clock_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    max_concurrency: int = Field(default=10, ge=1, le=100)
    max_queue_depth: int = Field(default=50, ge=1, le=500)
    per_tenant_max_concurrency: int = Field(default=4, ge=1, le=20)

    # Allowed storage prefix for immutable reference resolution
    allowed_storage_prefix: str = "ledgerai-evidence/"

    @model_validator(mode="after")
    def validate_security(self) -> Role6Settings:
        if self.allow_outbound_network and self.environment == "production":
            raise ValueError("Outbound network access must remain disabled in production")
        if self.environment == "production":
            if not self.service_token_secret:
                raise ValueError("service_token_secret is required in production")
            if len(self.service_token_secret.get_secret_value().encode()) < 32:
                raise ValueError("service_token_secret must be at least 32 bytes in production")
        return self


@lru_cache
def get_role6_settings() -> Role6Settings:
    return Role6Settings()
