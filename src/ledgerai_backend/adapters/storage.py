"""Private S3-compatible immutable object-storage adapter."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from ledgerai_backend.core.config import Settings
from ledgerai_backend.ports import StoredObject


class StorageObjectNotFound(Exception):
    pass


class S3ObjectStorage:
    def __init__(self, settings: Settings) -> None:
        if not all(
            (
                settings.storage_endpoint_url,
                settings.storage_access_key,
                settings.storage_secret_key,
            )
        ):
            raise ValueError("secure object-storage configuration is required")
        assert settings.storage_access_key is not None
        assert settings.storage_secret_key is not None
        self._bucket = settings.storage_bucket
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint_url,
            region_name=settings.storage_region,
            aws_access_key_id=settings.storage_access_key.get_secret_value(),
            aws_secret_access_key=settings.storage_secret_key.get_secret_value(),
            use_ssl=settings.storage_use_tls,
            config=Config(
                connect_timeout=2,
                read_timeout=10,
                retries={"max_attempts": 2, "mode": "standard"},
                signature_version="s3v4",
            ),
        )

    def create_upload_url(
        self, *, object_key: str, content_type: str, byte_size: int, expires_seconds: int
    ) -> str:
        return str(
            self._client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": object_key,
                    "ContentType": content_type,
                    "Metadata": {"expected-size": str(byte_size)},
                    "ServerSideEncryption": "AES256",
                },
                ExpiresIn=expires_seconds,
                HttpMethod="PUT",
            )
        )

    def stat_object(self, *, object_key: str) -> StoredObject:
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=object_key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                raise StorageObjectNotFound from exc
            raise
        metadata = response.get("Metadata", {})
        return StoredObject(
            byte_size=int(response["ContentLength"]),
            content_type=str(response.get("ContentType", "application/octet-stream")),
            sha256=str(metadata.get("sha256", "")),
            version_id=response.get("VersionId"),
            server_side_encryption=response.get("ServerSideEncryption"),
        )

    def read_object(self, *, object_key: str, maximum_bytes: int) -> bytes:
        try:
            response = self._client.get_object(
                Bucket=self._bucket, Key=object_key, Range=f"bytes=0-{maximum_bytes}"
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                raise StorageObjectNotFound from exc
            raise
        data = bytes(response["Body"].read(maximum_bytes + 1))
        if len(data) > maximum_bytes:
            raise ValueError("stored object exceeds configured maximum")
        return data

    @staticmethod
    def digest(content: bytes) -> str:
        return sha256(content).hexdigest()
