"""FastAPI application factory for Role 1 Document Intelligence."""

from __future__ import annotations

from fastapi import FastAPI

from ledgerai_role1.pipeline.pretrained_baseline import PretrainedDocumentExtractor
from ledgerai_role1.service.config import Role1Settings
from ledgerai_role1.service.idempotency import ExtractionIdempotencyStore
from ledgerai_role1.service.routes import router


def create_app(settings: Role1Settings | None = None) -> FastAPI:
    cfg = settings or Role1Settings()
    app = FastAPI(
        title="LedgerAI Role 1 Document Intelligence",
        version="1.0.0",
        docs_url="/docs" if cfg.environment != "production" else None,
        redoc_url=None,
    )

    app.state.settings = cfg
    app.state.idempotency_store = ExtractionIdempotencyStore()
    app.state.extractor = PretrainedDocumentExtractor()

    app.include_router(router)
    return app


app = create_app()
