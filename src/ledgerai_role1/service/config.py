"""Configuration settings for Role 1 Document Intelligence Service."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Role1Settings(BaseSettings):
    """Runtime configuration for Role 1 service."""

    model_config = SettingsConfigDict(
        env_prefix="LEDGERAI_ROLE1_",
        env_file=".env",
        extra="ignore",
    )

    service_name: str = "ledgerai-role1-document-intelligence"
    environment: str = "production"
    service_token_secret: SecretStr = Field(
        default=SecretStr("replace-with-at-least-32-random-bytes-for-role1-auth"),
        description="Shared secret for validating Role 4 service tokens",
    )
    audience: str = "role1"
    host: str = "0.0.0.0"
    port: int = 8101

    # Security limits
    max_request_bytes: int = 10_485_760  # 10 MB
    max_page_count: int = 10
    max_processing_time_seconds: float = 15.0
    allowed_media_types: tuple[str, ...] = (
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/tiff",
        "text/plain",
    )
    allowlisted_storage_prefix: str = "documents/"
