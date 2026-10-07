from __future__ import annotations

import os
from hashlib import sha256
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import pytest
import redis
from pydantic import SecretStr

from ledgerai_backend.adapters.queue import CeleryJobQueue
from ledgerai_backend.adapters.storage import S3ObjectStorage
from ledgerai_backend.core.config import Settings


def required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is required for external-service integration tests")
    return value


@pytest.mark.integration_service
def test_real_s3_compatible_private_storage_round_trip() -> None:
    endpoint = required_environment("LEDGERAI_TEST_STORAGE_ENDPOINT_URL")
    access_key = required_environment("LEDGERAI_TEST_STORAGE_ACCESS_KEY")
    secret_key = required_environment("LEDGERAI_TEST_STORAGE_SECRET_KEY")
    settings = Settings(
        environment="test",
        storage_endpoint_url=endpoint,
        storage_access_key=SecretStr(access_key),
        storage_secret_key=SecretStr(secret_key),
        storage_use_tls=endpoint.startswith("https://"),
    )
    storage = S3ObjectStorage(settings)
    object_key = f"quarantine/{uuid4()}/{uuid4()}/{uuid4()}"
    content = b"%PDF-1.7\nsynthetic minio evidence"
    url = storage.create_upload_url(
        object_key=object_key,
        content_type="application/pdf",
        byte_size=len(content),
        expires_seconds=60,
    )
    parsed = urlparse(url)
    assert parsed.scheme in {"http", "https"}
    assert secret_key not in url
    assert 0 < int(parse_qs(parsed.query)["X-Amz-Expires"][0]) <= 60
    response = httpx.put(
        url,
        content=content,
        headers={
            "Content-Type": "application/pdf",
            "x-amz-meta-expected-size": str(len(content)),
            "x-amz-server-side-encryption": "AES256",
        },
        timeout=10,
    )
    response.raise_for_status()
    stored = storage.stat_object(object_key=object_key)
    assert stored.byte_size == len(content)
    assert stored.server_side_encryption == "AES256"
    assert storage.read_object(object_key=object_key, maximum_bytes=1024) == content
    assert S3ObjectStorage.digest(content) == sha256(content).hexdigest()


@pytest.mark.integration_service
def test_real_redis_celery_dispatch_contains_references_only() -> None:
    redis_url = required_environment("LEDGERAI_TEST_REDIS_URL")
    client = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
    assert client.ping() is True
    queue = CeleryJobQueue(
        Settings(environment="test", redis_url=SecretStr(redis_url), queue_default="ledgerai.test")
    )
    job_id = uuid4()
    task_id = queue.enqueue(
        job_id=job_id,
        queue_name="ledgerai.test",
        correlation_id=uuid4(),
        event_id=uuid4(),
    )
    assert task_id == str(job_id)
