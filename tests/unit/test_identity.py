from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import SecretStr

from ledgerai_backend.core.config import Settings
from ledgerai_backend.core.identity import AuthenticationError, JwtIdentityProvider

ISSUER = "https://identity.test.invalid/"
AUDIENCE = "ledgerai-api"


@pytest.fixture(scope="module")
def keys() -> tuple[str, str]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def provider(public_key: str) -> JwtIdentityProvider:
    return JwtIdentityProvider(
        Settings(
            environment="test",
            jwt_issuer=ISSUER,
            jwt_audience=AUDIENCE,
            jwt_public_key=SecretStr(public_key),
            jwt_algorithms=["RS256"],
        )
    )


def token(private_key: str, **overrides: object) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "synthetic-user",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


@pytest.mark.asyncio
async def test_valid_token(keys: tuple[str, str]) -> None:
    private, public = keys
    identity = await provider(public).verify(token(private))
    assert identity.issuer == ISSUER
    assert identity.subject == "synthetic-user"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://wrong.invalid/"},
        {"aud": "wrong-audience"},
        {"exp": datetime.now(UTC) - timedelta(seconds=1)},
        {"nbf": datetime.now(UTC) + timedelta(minutes=5)},
        {"sub": ""},
    ],
)
async def test_invalid_claims_are_rejected(
    keys: tuple[str, str], overrides: dict[str, object]
) -> None:
    private, public = keys
    with pytest.raises(AuthenticationError):
        await provider(public).verify(token(private, **overrides))


@pytest.mark.asyncio
async def test_invalid_signature_is_rejected(keys: tuple[str, str]) -> None:
    _, public = keys
    other_private, _ = keys_for_test()
    with pytest.raises(AuthenticationError):
        await provider(public).verify(token(other_private))


@pytest.mark.asyncio
async def test_disallowed_algorithm_is_rejected(keys: tuple[str, str]) -> None:
    _, public = keys
    encoded = jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "synthetic",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "iat": datetime.now(UTC),
        },
        "test-only-secret-that-is-long-enough-for-hmac-testing",
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError):
        await provider(public).verify(encoded)


@pytest.mark.asyncio
async def test_malformed_token_is_rejected(keys: tuple[str, str]) -> None:
    _, public = keys
    with pytest.raises(AuthenticationError):
        await provider(public).verify("not-a-token")


@pytest.mark.asyncio
async def test_missing_required_claim_is_rejected(keys: tuple[str, str]) -> None:
    private, public = keys
    now = datetime.now(UTC)
    encoded = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + timedelta(minutes=5)},
        private,
        algorithm="RS256",
    )
    with pytest.raises(AuthenticationError):
        await provider(public).verify(encoded)


def keys_for_test() -> tuple[str, str]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        private.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode(),
    )
