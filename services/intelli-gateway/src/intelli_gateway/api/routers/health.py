"""Liveness and readiness."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from intelli_gateway.api.dependencies import get_database
from intelli_gateway.schemas.api_models.responses import HealthResponse, ReadinessResponse
from intelli_gateway.services.postgres.database import database_is_reachable

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse, summary="Liveness")
async def healthz() -> HealthResponse:
    """Dependency-free liveness check (the Docker HEALTHCHECK hits it)."""
    return HealthResponse(ok=True)


@router.get(
    "/readyz",
    response_model=ReadinessResponse,
    summary="Readiness",
    responses={503: {"model": ReadinessResponse, "description": "The database is unreachable"}},
)
async def readyz(
    database: AsyncEngine | None = Depends(get_database),
) -> ReadinessResponse | JSONResponse:
    """Ready to serve: its own Postgres answers (when one is configured). The deploy waits on it."""
    if database is None:
        return ReadinessResponse(ok=True, database="not_configured")
    if await database_is_reachable(database):
        return ReadinessResponse(ok=True, database="ok")
    body = ReadinessResponse(ok=False, database="unavailable")
    return JSONResponse(status_code=503, content=body.model_dump())
