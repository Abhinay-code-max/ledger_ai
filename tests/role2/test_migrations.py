"""Tests for Alembic migration upgrade, downgrade, and re-upgrade cycles."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]


def get_alembic_config(dsn: str | None = None) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    if dsn:
        config.set_main_option("sqlalchemy.url", dsn)
    return config


def test_migration_chain_and_revisions() -> None:
    """Verify that migration revisions form a contiguous, non-branching chain."""
    import importlib
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    m1 = importlib.import_module("migrations.versions.20261006_01_phase1_foundation")
    m2 = importlib.import_module("migrations.versions.20261006_02_secure_ingestion")
    m3 = importlib.import_module("migrations.versions.20261007_03_service_integration")
    m4 = importlib.import_module("migrations.versions.20261008_04_accounting_assurance")
    m5 = importlib.import_module("migrations.versions.20261011_05_accounting_core")

    assert m1.down_revision is None
    assert m2.down_revision == m1.revision
    assert m3.down_revision == m2.revision
    assert m4.down_revision == m3.revision
    assert m5.down_revision == m4.revision
    assert m5.revision == "20261011_05"


def test_role2_tables_in_target_metadata() -> None:
    """Verify that target metadata contains all expected Role 2 tables."""
    from ledgerai_backend.database.base import Base

    table_names = set(Base.metadata.tables.keys())
    expected = {
        "role2_accounts",
        "role2_accounting_periods",
        "role2_posting_operations",
        "role2_posted_journals",
        "role2_journal_lines",
        "role2_period_close_operations",
        "role2_statement_snapshots",
        "role2_statement_lines",
        "role2_proposal_registry",
    }
    assert expected.issubset(table_names)


@pytest.mark.postgres
def test_live_postgres_migration_lifecycle() -> None:
    """Run upgrade -> downgrade -> re-upgrade cycle against real PostgreSQL database."""
    dsn = os.getenv("LEDGERAI_TEST_ADMIN_DSN") or os.getenv("LEDGERAI_MIGRATION_DSN")
    if not dsn:
        pytest.skip(
            "LEDGERAI_TEST_ADMIN_DSN or LEDGERAI_MIGRATION_DSN is required for live migration test"
        )

    cfg = get_alembic_config(dsn)

    # Upgrade to head
    command.upgrade(cfg, "20261011_05")

    # Downgrade to previous revision
    command.downgrade(cfg, "20261008_04")

    # Re-upgrade to head
    command.upgrade(cfg, "20261011_05")
