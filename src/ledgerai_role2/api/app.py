"""FastAPI application factory for Role 2 Accounting Core."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role2.api.routes import router
from ledgerai_role2.config import Role2Settings
from ledgerai_role2.database.in_memory import InMemoryRole2Repository
from ledgerai_role2.security.middleware import Role2SecurityMiddleware


def create_role2_app(
    settings: Role2Settings | None = None,
    repository_factory: Callable[[EntityTenantContext], Any] | None = None,
) -> FastAPI:
    cfg = settings or Role2Settings()

    app = FastAPI(
        title="LedgerAI Role 2: Deterministic Accounting Core",
        description=(
            "Deterministic, exact, explainable, and independently testable "
            "double-entry accounting engine."
        ),
        version=cfg.service_version,
    )

    # Attach settings
    app.state.settings = cfg

    # Shared store for in-memory repository if using default factory
    shared_store: dict[str, Any] = {
        "accounts": {},
        "periods": {},
        "proposals": {},
        "posting_ops": {},
        "close_ops": {},
        "journals": {},
        "journal_lines": {},
        "snapshots": {},
        "statement_lines": {},
    }

    if repository_factory is None:

        def default_factory(ctx: EntityTenantContext) -> InMemoryRole2Repository:
            return InMemoryRole2Repository(ctx, shared_store=shared_store)

        app.state.get_repository = default_factory
    else:
        app.state.get_repository = repository_factory

    # Security middleware
    app.add_middleware(
        Role2SecurityMiddleware,
        max_request_bytes=cfg.max_request_bytes,
        concurrency_limit=cfg.concurrency_limit,
    )

    # Custom exception handlers for clean JSON errors without leaking internals
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        content = (
            exc.detail
            if isinstance(exc.detail, dict)
            else {"code": "HTTP_ERROR", "message": str(exc.detail)}
        )
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "code": "SCHEMA_VALIDATION_ERROR",
                "message": "The request payload does not conform to the schema.",
                "errors": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()[:10]],
            },
        )

    app.include_router(router)
    return app
