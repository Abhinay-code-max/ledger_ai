"""Liveness and dependency-aware readiness without connection detail leakage."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter()


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(request: Request) -> JSONResponse:
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    if request.app.state.settings.environment == "production" and any(
        getattr(request.app.state, dependency, None) is None
        for dependency in ("object_storage", "malware_scanner", "job_queue")
    ):
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(content={"status": "ok"})
