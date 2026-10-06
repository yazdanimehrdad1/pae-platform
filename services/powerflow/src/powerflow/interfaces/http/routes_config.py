"""The active site config: /config. Stored sites are edited under /sites; the JSON Schema is at
/schemas/site-config."""

from fastapi import APIRouter, Depends

from powerflow.interfaces.base import AdapterContext
from powerflow.interfaces.http.dependencies import get_context
from powerflow.site_config import SiteConfig

router = APIRouter(tags=["config"])


@router.get(
    "/config",
    response_model=SiteConfig,
    summary="The active site config",
    description="To change it: PUT /api/sites/{name}, then POST /api/sites/{name}/activate.",
)
async def get_config(context: AdapterContext = Depends(get_context)) -> SiteConfig:
    return context.engine.config
