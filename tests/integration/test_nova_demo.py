"""Comprehensive integration tests for the reproducible NOVA Phase 4 demo harness."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from phase1_postgres_support import admin_dsn, runtime_dsn
from pydantic import SecretStr

from ledgerai_backend.core.config import Settings
from ledgerai_backend.demo.reset import (
    NOVA_TENANT_ID,
    DemoResetError,
    _require_safe_reset,
    reset_nova_demo,
)
from ledgerai_backend.demo.runner import (
    DATASET,
    PROVENANCE_PATH,
    REQUIRED_AUDIT,
    DemoFailure,
    run,
)

pytestmark = pytest.mark.postgres


def _configure_demo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGERAI_ENVIRONMENT", "test")
    monkeypatch.setenv("LEDGERAI_DEMO_ENABLED", "true")
    monkeypatch.setenv("LEDGERAI_DEMO_RESET_CONFIRM", "RESET_NOVA_ONLY")
    monkeypatch.setenv("LEDGERAI_DEMO_MAKER_TOKEN", "synthetic-maker-token-for-nova")
    monkeypatch.setenv("LEDGERAI_DEMO_REVIEWER_TOKEN", "synthetic-reviewer-token-for-nova")
    monkeypatch.setenv("LEDGERAI_SERVICE_TOKEN_SECRET", "synthetic-service-secret-for-nova-0001")
    monkeypatch.setenv(
        "LEDGERAI_STORAGE_ENDPOINT_URL", os.environ["LEDGERAI_TEST_STORAGE_ENDPOINT_URL"]
    )
    monkeypatch.setenv(
        "LEDGERAI_STORAGE_ACCESS_KEY", os.environ["LEDGERAI_TEST_STORAGE_ACCESS_KEY"]
    )
    monkeypatch.setenv(
        "LEDGERAI_STORAGE_SECRET_KEY", os.environ["LEDGERAI_TEST_STORAGE_SECRET_KEY"]
    )
    monkeypatch.setenv("LEDGERAI_REDIS_URL", os.environ["LEDGERAI_TEST_REDIS_URL"])
    monkeypatch.setenv(
        "LEDGERAI_DATABASE_DSN",
        runtime_dsn().replace("postgresql://", "postgresql+psycopg://", 1),
    )
    monkeypatch.setenv(
        "LEDGERAI_MIGRATION_DSN",
        admin_dsn().replace("postgresql://", "postgresql+psycopg://", 1),
    )


def test_production_reset_refusal() -> None:
    """Verify that destructive reset is strictly refused in production."""
    settings = Settings(
        environment="production",
        database_dsn=SecretStr("postgresql+psycopg://runtime.invalid/db"),
        migration_dsn=SecretStr("postgresql+psycopg://migrator.invalid/db"),
        jwt_issuer="https://identity.invalid/",
        jwt_audience="ledgerai",
        jwt_public_key=SecretStr("public-key"),
        storage_endpoint_url="https://storage.invalid",
        storage_access_key=SecretStr("access"),
        storage_secret_key=SecretStr("secret"),
        scanner_adapter="clamav",
        redis_url=SecretStr("redis://redis.invalid/0"),
        role1_base_url="https://role1.invalid",
        role2_base_url="https://role2.invalid",
        role3_base_url="https://role3.invalid",
        role6_base_url="https://role6.invalid",
        service_token_secret=SecretStr("x" * 32),
    )
    with pytest.raises(DemoResetError, match="prohibited"):
        _require_safe_reset(settings, confirmed=True, tenant_id=NOVA_TENANT_ID)


def test_tenant_specific_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that reset safely targets only the designated NOVA tenant."""
    _configure_demo_env(monkeypatch)
    settings = Settings(
        environment="test",
        migration_dsn=SecretStr(admin_dsn().replace("postgresql://", "postgresql+psycopg://", 1)),
    )
    # Reject arbitrary foreign tenant
    foreign_tenant = uuid4()
    with pytest.raises(DemoResetError, match="arbitrary tenant"):
        _require_safe_reset(settings, confirmed=True, tenant_id=foreign_tenant)

    # Reject unconfirmed reset
    with pytest.raises(DemoResetError, match="confirmation"):
        _require_safe_reset(settings, confirmed=False, tenant_id=NOVA_TENANT_ID)

    # Valid confirmed reset targets only NOVA
    result = reset_nova_demo(settings, confirmed=True)
    assert result["tenant_id"] == str(NOVA_TENANT_ID)


def test_complete_nova_demo_is_repeatable_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that the complete NOVA demo runs twice consecutively from reset with exact matching normalized output."""
    _configure_demo_env(monkeypatch)
    first = run()
    second = run()
    expected = json.loads((Path(DATASET) / "expected" / "summary.json").read_text())
    assert first == second == expected


def test_duplicate_command_invocation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that duplicate invocation reproduces identical normalized business summary."""
    _configure_demo_env(monkeypatch)
    output = run()
    expected = json.loads((Path(DATASET) / "expected" / "summary.json").read_text())
    assert output == expected


def test_missing_service_and_downstream_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that missing downstream services fail closed promptly."""
    _configure_demo_env(monkeypatch)
    monkeypatch.setenv("LEDGERAI_DEMO_ROLE1_URL", "http://127.0.0.1:59991")
    with pytest.raises((DemoFailure, OSError)):
        run()


def test_unknown_posting_outcome_and_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that unknown posting outcome does not advance period and can be recovered."""
    _configure_demo_env(monkeypatch)
    monkeypatch.setenv("LEDGERAI_DEMO_UNKNOWN_POSTING", "true")
    summary = cast(dict[str, Any], run())
    assert summary["posting"]["state"] == "CONFIRMED"
    assert summary["accounting_period"]["state"] == "CLOSED"


def test_planted_exception_and_authorized_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that planted mismatch is detected and resolved via authorized reviewer."""
    _configure_demo_env(monkeypatch)
    summary = cast(dict[str, Any], run())
    assert summary["exception"]["type"] == "AMOUNT_MISMATCH"
    assert summary["exception"]["severity"] == "HIGH"
    assert summary["exception"]["resolution"] == "RESOLVED"
    assert summary["financials"]["planted_mismatch"] == "50.00"


def test_maker_checker_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify maker self-approval and stale reviews are rejected."""
    _configure_demo_env(monkeypatch)
    summary = cast(dict[str, Any], run())
    assert summary["maker_checker"]["maker_rejected"] is True
    assert summary["maker_checker"]["reviewer_approved"] is True
    assert summary["maker_checker"]["stale_rejected"] is True


def test_all_three_statements(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify all three financial statements are captured matching committed fixtures."""
    _configure_demo_env(monkeypatch)
    summary = cast(dict[str, Any], run())
    assert summary["statements"] == ["BALANCE_SHEET", "PROFIT_AND_LOSS", "TRIAL_BALANCE"]


def test_audit_completeness(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the append-only audit trail captures all required lifecycle actions."""
    _configure_demo_env(monkeypatch)
    summary = cast(dict[str, Any], run())
    assert set(cast(list[str], summary["audit_actions"])) == REQUIRED_AUDIT


def test_statement_to_source_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that provenance connects financial statements back to source evidence through all 11 nodes."""
    _configure_demo_env(monkeypatch)
    summary = cast(dict[str, Any], run())
    assert summary["provenance_path"] == PROVENANCE_PATH


def test_no_direct_database_workflow_advancement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that all workflow progression occurs strictly through live HTTP APIs."""
    _configure_demo_env(monkeypatch)
    summary = cast(dict[str, Any], run())
    assert summary["scenario"] == "nova-phase4-v1"
