"""Secure typed HTTP adapters for independently owned Role services."""

from __future__ import annotations

import asyncio
import hmac
import json
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic, time
from typing import Any, Generic, Protocol, TypeVar, cast
from urllib.parse import urljoin, urlsplit
from uuid import UUID

import httpx
import jwt
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ledgerai_backend.core.observability import (
    adapter_calls,
    adapter_contract_rejections,
    adapter_latency,
    circuit_events,
)
from ledgerai_contracts.v1.accounting import (
    AccountingValidationResult,
    FinancialStatementSnapshot,
    JournalPostingResult,
    PeriodCloseResult,
    PeriodCloseValidationResult,
    PostingStatusResult,
)
from ledgerai_contracts.v1.documents import DocumentExtraction
from ledgerai_contracts.v1.exceptions import ExceptionRecord
from ledgerai_contracts.v1.reconciliation import MatchProposal
from ledgerai_contracts.v1.tenancy import EntityTenantContext

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class AdapterError(RuntimeError):
    """Safe adapter failure with stable classification."""

    def __init__(self, code: str, *, retryable: bool = False, unknown_outcome: bool = False):
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.unknown_outcome = unknown_outcome


class ServiceTokenProvider(Protocol):
    def token(self, *, audience: str, tenant_id: UUID, operation_id: UUID) -> str: ...


class SignedServiceTokenProvider:
    """Issue a short-lived HS256 service token from a dedicated service secret."""

    def __init__(self, *, issuer: str, subject: str, secret: str, ttl_seconds: int = 60) -> None:
        if len(secret.encode()) < 32:
            raise ValueError("service token secret must be at least 32 bytes")
        if ttl_seconds < 10 or ttl_seconds > 300:
            raise ValueError("service token lifetime must be between 10 and 300 seconds")
        self._issuer, self._subject, self._secret, self._ttl = issuer, subject, secret, ttl_seconds

    def token(self, *, audience: str, tenant_id: UUID, operation_id: UUID) -> str:
        now = int(time())
        return jwt.encode(
            {
                "iss": self._issuer,
                "sub": self._subject,
                "aud": audience,
                "iat": now,
                "exp": now + self._ttl,
                "tenant_id": str(tenant_id),
                "operation_id": str(operation_id),
            },
            self._secret,
            algorithm="HS256",
        )


@dataclass(frozen=True, slots=True)
class AdapterSecurity:
    base_url: str
    audience: str
    environment: str = "production"
    connect_timeout: float = 2.0
    read_timeout: float = 15.0
    write_timeout: float = 5.0
    pool_timeout: float = 2.0
    total_timeout: float = 20.0
    maximum_response_bytes: int = 1_048_576
    maximum_attempts: int = 3
    circuit_failure_threshold: int = 5
    circuit_reset_seconds: float = 30.0

    def __post_init__(self) -> None:
        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("service base URL must be an absolute credential-free HTTP(S) URL")
        if parsed.query or parsed.fragment:
            raise ValueError("service base URL cannot contain a query or fragment")
        if self.environment == "production" and parsed.scheme != "https":
            raise ValueError("production service adapters require HTTPS")
        if self.maximum_response_bytes < 1024 or self.maximum_response_bytes > 10_485_760:
            raise ValueError("invalid response size limit")
        if self.maximum_attempts < 1 or self.maximum_attempts > 5:
            raise ValueError("invalid adapter attempt limit")


class _Circuit:
    def __init__(self, threshold: int, reset_seconds: float) -> None:
        self.threshold, self.reset_seconds = threshold, reset_seconds
        self.failures = 0
        self.opened_at: float | None = None

    def before(self) -> None:
        if self.opened_at is None:
            return
        if monotonic() - self.opened_at >= self.reset_seconds:
            self.opened_at = None
            self.failures = 0
            return
        raise AdapterError("CIRCUIT_OPEN", retryable=True)

    def success(self) -> None:
        self.failures, self.opened_at = 0, None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = monotonic()


def _unique_json(data: bytes) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise AdapterError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    try:
        return json.loads(
            data,
            object_pairs_hook=pairs,
            parse_float=lambda _: (_ for _ in ()).throw(AdapterError("FLOAT_NOT_ALLOWED")),
        )
    except AdapterError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterError("MALFORMED_JSON") from exc


class SecureRoleAdapter(Generic[ResponseModel]):
    def __init__(
        self,
        security: AdapterSecurity,
        token_provider: ServiceTokenProvider,
        *,
        response_model: type[ResponseModel],
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Any] = asyncio.sleep,
    ) -> None:
        self.security = security
        self.token_provider = token_provider
        self.response_model = response_model
        self._origin = urlsplit(security.base_url)
        self._client = client or httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(
                connect=security.connect_timeout,
                read=security.read_timeout,
                write=security.write_timeout,
                pool=security.pool_timeout,
            ),
        )
        self._owns_client = client is None
        self._sleep = sleep
        self._circuit = _Circuit(security.circuit_failure_threshold, security.circuit_reset_seconds)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def call(
        self,
        *,
        path: str,
        payload: Mapping[str, object],
        tenant_context: EntityTenantContext,
        operation_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        expected_resource: tuple[str, UUID] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> ResponseModel:
        if not path.startswith("/") or ".." in path or "?" in path or "#" in path:
            raise ValueError("adapter path is not a fixed safe path")
        url = urljoin(self.security.base_url.rstrip("/") + "/", path.lstrip("/"))
        target = urlsplit(url)
        if (target.scheme, target.hostname, target.port) != (
            self._origin.scheme,
            self._origin.hostname,
            self._origin.port,
        ):
            raise AdapterError("UNTRUSTED_DESTINATION")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "Bearer "
            + self.token_provider.token(
                audience=self.security.audience,
                tenant_id=tenant_context.tenant_id,
                operation_id=operation_id,
            ),
            "X-Operation-ID": str(operation_id),
            "X-Correlation-ID": str(correlation_id),
            "X-Tenant-ID": str(tenant_context.tenant_id),
            "X-Organization-ID": str(tenant_context.organization_id),
            "X-Legal-Entity-ID": str(tenant_context.legal_entity_id),
        }
        if causation_id:
            headers["X-Causation-ID"] = str(causation_id)
        last: AdapterError | None = None
        call_started = monotonic()
        for attempt in range(1, self.security.maximum_attempts + 1):
            try:
                self._circuit.before()
            except AdapterError:
                circuit_events.add(1, {"state": "open"})
                adapter_calls.add(1, {"service": self.security.audience, "outcome": "circuit_open"})
                raise
            try:
                response = await asyncio.wait_for(
                    self._client.post(url, headers=headers, json=dict(payload)),
                    timeout=self.security.total_timeout,
                )
                if 300 <= response.status_code < 400:
                    raise AdapterError("REDIRECT_REJECTED")
                if response.status_code in {408, 425, 429, 502, 503, 504}:
                    raise AdapterError(
                        "TRANSIENT_DOWNSTREAM_FAILURE",
                        retryable=True,
                        unknown_outcome=response.status_code in {408, 504},
                    )
                if response.status_code in {401, 403}:
                    raise AdapterError("SERVICE_AUTHENTICATION_FAILED")
                if response.status_code >= 400:
                    raise AdapterError("TERMINAL_DOWNSTREAM_FAILURE")
                if response.headers.get("content-encoding", "identity").lower() not in {
                    "",
                    "identity",
                }:
                    raise AdapterError("COMPRESSED_RESPONSE_REJECTED")
                content_type = (
                    response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                )
                if content_type != "application/json":
                    raise AdapterError("INVALID_CONTENT_TYPE")
                body = response.content
                if len(body) > self.security.maximum_response_bytes:
                    raise AdapterError("RESPONSE_TOO_LARGE")
                raw = _unique_json(body)
                try:
                    result = (response_model or self.response_model).model_validate(raw)
                except ValidationError as exc:
                    raise AdapterError("CONTRACT_REJECTED") from exc
                typed_result = cast(ResponseModel, result)
                self._verify_context(typed_result, tenant_context)
                if expected_resource:
                    serialized = json.dumps(result.model_dump(mode="json"), separators=(",", ":"))
                    if str(expected_resource[1]) not in serialized:
                        raise AdapterError("WRONG_WORKFLOW_RESOURCE")
                self._circuit.success()
                adapter_calls.add(1, {"service": self.security.audience, "outcome": "success"})
                adapter_latency.record(
                    monotonic() - call_started,
                    {"service": self.security.audience, "outcome": "success"},
                )
                return typed_result
            except (httpx.TimeoutException, httpx.NetworkError, TimeoutError) as exc:
                last = AdapterError("DOWNSTREAM_TIMEOUT", retryable=True, unknown_outcome=True)
                self._circuit.failure()
                if attempt == self.security.maximum_attempts:
                    adapter_calls.add(1, {"service": self.security.audience, "outcome": "timeout"})
                    raise last from exc
            except AdapterError as exc:
                last = exc
                if not exc.retryable:
                    self._circuit.failure()
                    adapter_calls.add(
                        1, {"service": self.security.audience, "outcome": "terminal_failure"}
                    )
                    if exc.code in {
                        "CONTRACT_REJECTED",
                        "TENANT_CONTEXT_MISMATCH",
                        "WRONG_WORKFLOW_RESOURCE",
                        "DUPLICATE_JSON_KEY",
                    }:
                        adapter_contract_rejections.add(1, {"reason": exc.code})
                    raise
                self._circuit.failure()
                if attempt == self.security.maximum_attempts:
                    adapter_calls.add(
                        1, {"service": self.security.audience, "outcome": "retry_exhausted"}
                    )
                    raise
            delay = min(2.0, 0.1 * (2 ** (attempt - 1)))
            await self._sleep(
                delay + random.Random(operation_id.int + attempt).uniform(0, delay / 4)
            )
        assert last is not None
        raise last

    @staticmethod
    def _verify_context(result: ResponseModel, expected: EntityTenantContext) -> None:
        actual = getattr(result, "tenant_context", None)
        if actual != expected:
            raise AdapterError("TENANT_CONTEXT_MISMATCH")


class Role1Adapter(SecureRoleAdapter[DocumentExtraction]):
    def __init__(
        self, security: AdapterSecurity, token_provider: ServiceTokenProvider, **kwargs: Any
    ) -> None:
        super().__init__(security, token_provider, response_model=DocumentExtraction, **kwargs)

    async def request_extraction(self, **kwargs: Any) -> DocumentExtraction:
        return await self.call(path="/v1/extractions", **kwargs)


class ReconciliationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(pattern=r"^1\.0$")
    tenant_context: EntityTenantContext
    proposal: MatchProposal
    exceptions: list[ExceptionRecord] = Field(default_factory=list, max_length=100)


class Role3Adapter(SecureRoleAdapter[ReconciliationResult]):
    def __init__(
        self, security: AdapterSecurity, token_provider: ServiceTokenProvider, **kwargs: Any
    ) -> None:
        super().__init__(security, token_provider, response_model=ReconciliationResult, **kwargs)

    async def request_reconciliation(self, **kwargs: Any) -> ReconciliationResult:
        return await self.call(path="/v1/reconciliations", **kwargs)


class AccountingAcceptance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(pattern=r"^1\.0$")
    tenant_context: EntityTenantContext
    operation_id: UUID
    proposal_id: UUID
    proposal_version: str
    accepted: bool
    validation_reference: str | None = Field(default=None, max_length=200)


class Role2Adapter(SecureRoleAdapter[AccountingAcceptance]):
    def __init__(
        self, security: AdapterSecurity, token_provider: ServiceTokenProvider, **kwargs: Any
    ) -> None:
        super().__init__(security, token_provider, response_model=AccountingAcceptance, **kwargs)

    async def request_posting_validation(self, **kwargs: Any) -> AccountingAcceptance:
        return await self.call(path="/v1/journal-posting-requests", **kwargs)

    async def validate_posting(self, **kwargs: Any) -> AccountingValidationResult:
        return cast(
            AccountingValidationResult,
            await self.call(
                path="/v1/accounting-validations",
                response_model=AccountingValidationResult,
                **kwargs,
            ),
        )

    async def post_journal(self, **kwargs: Any) -> JournalPostingResult:
        return cast(
            JournalPostingResult,
            await self.call(
                path="/v1/journal-postings", response_model=JournalPostingResult, **kwargs
            ),
        )

    async def posting_status(self, **kwargs: Any) -> PostingStatusResult:
        return cast(
            PostingStatusResult,
            await self.call(
                path="/v1/journal-posting-status",
                response_model=PostingStatusResult,
                **kwargs,
            ),
        )

    async def validate_period_close(self, **kwargs: Any) -> PeriodCloseValidationResult:
        return cast(
            PeriodCloseValidationResult,
            await self.call(
                path="/v1/period-close-validations",
                response_model=PeriodCloseValidationResult,
                **kwargs,
            ),
        )

    async def close_period(self, **kwargs: Any) -> PeriodCloseResult:
        return cast(
            PeriodCloseResult,
            await self.call(path="/v1/period-closes", response_model=PeriodCloseResult, **kwargs),
        )

    async def period_close_status(self, **kwargs: Any) -> PeriodCloseResult:
        return cast(
            PeriodCloseResult,
            await self.call(
                path="/v1/period-close-status", response_model=PeriodCloseResult, **kwargs
            ),
        )

    async def financial_statement(self, **kwargs: Any) -> FinancialStatementSnapshot:
        return cast(
            FinancialStatementSnapshot,
            await self.call(
                path="/v1/financial-statements",
                response_model=FinancialStatementSnapshot,
                **kwargs,
            ),
        )


class Role6Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(pattern=r"^1\.0$")
    tenant_context: EntityTenantContext
    resource_id: UUID
    category: str = Field(min_length=1, max_length=100)
    confidence: str = Field(pattern=r"^(?:0(?:\.\d+)?|1(?:\.0+)?)$")
    provenance: list[dict[str, object]] = Field(min_length=1, max_length=100)


class Role6Adapter(SecureRoleAdapter[Role6Classification]):
    def __init__(
        self, security: AdapterSecurity, token_provider: ServiceTokenProvider, **kwargs: Any
    ) -> None:
        super().__init__(security, token_provider, response_model=Role6Classification, **kwargs)

    async def classify(self, **kwargs: Any) -> Role6Classification:
        return await self.call(path="/v1/classifications", **kwargs)


def verify_webhook_signature(body: bytes, *, signature: str, secret: bytes) -> bool:
    """Constant-time verification helper for signed asynchronous service callbacks."""
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret, body, sha256).hexdigest()
    return hmac.compare_digest(signature[7:], expected)
