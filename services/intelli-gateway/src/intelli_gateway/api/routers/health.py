"""Liveness."""

from fastapi import APIRouter

from intelli_gateway.schemas.api_models.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse, summary="Liveness")
async def healthz() -> HealthResponse:
    """Dependency-free liveness check (the Docker HEALTHCHECK hits it)."""
    return HealthResponse(ok=True)
