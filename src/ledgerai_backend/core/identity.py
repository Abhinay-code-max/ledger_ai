"""External identity verification boundary."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from ledgerai_backend.core.config import Settings


class AuthenticationError(Exception):
    """A deliberately detail-free authentication failure."""


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    issuer: str
    subject: str


class IdentityProviderPort(Protocol):
    async def verify(self, token: str) -> VerifiedIdentity: ...


class JwtIdentityProvider:
    """Verify asymmetric JWTs, including rotated JWKS keys when configured."""

    def __init__(self, settings: Settings) -> None:
        if not settings.jwt_issuer or not settings.jwt_audience:
            raise ValueError("JWT issuer and audience are required")
        if not (settings.jwks_url or settings.jwt_public_key):
            raise ValueError("JWKS URL or public key is required")
        self._issuer = settings.jwt_issuer
        self._audience = settings.jwt_audience
        self._algorithms = tuple(settings.jwt_algorithms)
        self._public_key = (
            settings.jwt_public_key.get_secret_value() if settings.jwt_public_key else None
        )
        self._jwks = (
            PyJWKClient(
                settings.jwks_url,
                cache_keys=True,
                cache_jwk_set=True,
                lifespan=300,
                timeout=2,
            )
            if settings.jwks_url
            else None
        )

    def _verify_sync(self, token: str) -> VerifiedIdentity:
        try:
            unverified = jwt.get_unverified_header(token)
            algorithm = unverified.get("alg")
            if not isinstance(algorithm, str) or algorithm not in self._algorithms:
                raise AuthenticationError
            if algorithm.lower() == "none":
                raise AuthenticationError
            key: Any
            if self._jwks:
                key = self._jwks.get_signing_key_from_jwt(token).key
            elif self._public_key:
                key = self._public_key
            else:  # pragma: no cover - constructor prevents this state
                raise AuthenticationError
            claims = jwt.decode(
                token,
                key=key,
                algorithms=list(self._algorithms),
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
            subject = claims.get("sub")
            issuer = claims.get("iss")
            if not isinstance(subject, str) or not subject.strip() or not isinstance(issuer, str):
                raise AuthenticationError
            return VerifiedIdentity(issuer=issuer, subject=subject)
        except AuthenticationError:
            raise
        except (InvalidTokenError, ValueError, KeyError, TypeError) as exc:
            raise AuthenticationError from exc

    async def verify(self, token: str) -> VerifiedIdentity:
        return await asyncio.to_thread(self._verify_sync, token)


class DeterministicTestIdentityProvider:
    """Explicit dependency-injected test adapter; never selected by production settings."""

    def __init__(self, identities: dict[str, VerifiedIdentity]) -> None:
        self._identities = identities

    async def verify(self, token: str) -> VerifiedIdentity:
        try:
            return self._identities[token]
        except KeyError as exc:
            raise AuthenticationError from exc
