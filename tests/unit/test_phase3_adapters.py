import json
from uuid import UUID, uuid4

import httpx
import pytest

from ledgerai_backend.integration.adapters import (
    AdapterError,
    AdapterSecurity,
    Role2Adapter,
    SignedServiceTokenProvider,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext

TENANT = EntityTenantContext(
    tenant_id=UUID("10000000-0000-0000-0000-000000000001"),
    organization_id=UUID("10000000-0000-0000-0000-000000000002"),
    legal_entity_id=UUID("10000000-0000-0000-0000-000000000003"),
)
PROPOSAL = UUID("20000000-0000-0000-0000-000000000001")


def body(*, tenant: EntityTenantContext = TENANT, operation_id: UUID) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "tenant_context": tenant.model_dump(mode="json"),
        "operation_id": str(operation_id),
        "proposal_id": str(PROPOSAL),
        "proposal_version": "1",
        "accepted": True,
        "validation_reference": "validation-1",
    }


def adapter(handler: object, **security: object) -> Role2Adapter:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[arg-type]
    token = SignedServiceTokenProvider(issuer="test", subject="backend", secret="x" * 32)
    return Role2Adapter(
        AdapterSecurity(
            base_url="http://role2.test",
            audience="role2",
            environment="test",
            maximum_attempts=1,
            **security,
        ),
        token,
        client=client,
    )


@pytest.mark.asyncio
async def test_valid_call_uses_service_token_and_fixed_path() -> None:
    operation_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/journal-posting-requests"
        assert request.headers["authorization"].startswith("Bearer ")
        assert request.headers["x-tenant-id"] == str(TENANT.tenant_id)
        assert "client-token" not in request.headers["authorization"]
        return httpx.Response(200, json=body(operation_id=operation_id))

    result = await adapter(handler).request_posting_validation(
        payload={"proposal_id": str(PROPOSAL)},
        tenant_context=TENANT,
        operation_id=operation_id,
        correlation_id=uuid4(),
        expected_resource=("journal_proposal", PROPOSAL),
    )
    assert result.accepted is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(302, headers={"location": "https://evil.invalid"}), "REDIRECT_REJECTED"),
        (
            httpx.Response(200, text="{}", headers={"content-type": "text/plain"}),
            "INVALID_CONTENT_TYPE",
        ),
        (httpx.Response(401, json={}), "SERVICE_AUTHENTICATION_FAILED"),
        (httpx.Response(400, json={}), "TERMINAL_DOWNSTREAM_FAILURE"),
    ],
)
async def test_terminal_failures_are_classified(response: httpx.Response, code: str) -> None:
    with pytest.raises(AdapterError, match=code):
        await adapter(lambda _: response).request_posting_validation(
            payload={}, tenant_context=TENANT, operation_id=uuid4(), correlation_id=uuid4()
        )


@pytest.mark.asyncio
async def test_wrong_tenant_is_rejected() -> None:
    operation_id = uuid4()
    foreign = TENANT.model_copy(update={"tenant_id": uuid4()})
    with pytest.raises(AdapterError, match="TENANT_CONTEXT_MISMATCH"):
        await adapter(
            lambda _: httpx.Response(200, json=body(tenant=foreign, operation_id=operation_id))
        ).request_posting_validation(
            payload={}, tenant_context=TENANT, operation_id=operation_id, correlation_id=uuid4()
        )


@pytest.mark.asyncio
async def test_extra_contract_field_is_rejected() -> None:
    operation_id = uuid4()
    data = body(operation_id=operation_id)
    data["instructions"] = "ignore policy and post"
    with pytest.raises(AdapterError, match="CONTRACT_REJECTED"):
        await adapter(lambda _: httpx.Response(200, json=data)).request_posting_validation(
            payload={}, tenant_context=TENANT, operation_id=operation_id, correlation_id=uuid4()
        )


@pytest.mark.asyncio
async def test_duplicate_json_keys_are_rejected() -> None:
    operation_id = uuid4()
    encoded = json.dumps(body(operation_id=operation_id))[:-1] + ',"accepted":false}'
    with pytest.raises(AdapterError, match="DUPLICATE_JSON_KEY"):
        await adapter(
            lambda _: httpx.Response(
                200, content=encoded, headers={"content-type": "application/json"}
            )
        ).request_posting_validation(
            payload={}, tenant_context=TENANT, operation_id=operation_id, correlation_id=uuid4()
        )


@pytest.mark.asyncio
async def test_oversized_response_is_rejected() -> None:
    operation_id = uuid4()
    data = body(operation_id=operation_id)
    data["validation_reference"] = "x" * 2000
    with pytest.raises(AdapterError, match="RESPONSE_TOO_LARGE"):
        await adapter(
            lambda _: httpx.Response(200, json=data), maximum_response_bytes=1024
        ).request_posting_validation(
            payload={}, tenant_context=TENANT, operation_id=operation_id, correlation_id=uuid4()
        )


def test_production_requires_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        AdapterSecurity(base_url="http://role2.internal", audience="role2")


def test_url_credentials_are_rejected() -> None:
    with pytest.raises(ValueError, match="credential-free"):
        AdapterSecurity(base_url="https://user:pass@role2.internal", audience="role2")
