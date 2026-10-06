"""Async database engine lifecycle."""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from ledgerai_backend.core.config import Settings

if sys.platform == "win32":
    # psycopg async requires selector readiness APIs unavailable on ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def create_engine(settings: Settings) -> AsyncEngine:
    if not settings.database_dsn:
        raise ValueError("database_dsn is required")
    return create_async_engine(
        settings.database_dsn.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=300,
    )
