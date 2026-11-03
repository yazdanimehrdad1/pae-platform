"""Site profile endpoints: the registered profiles a site can be given (sites.profile)."""

from fastapi import APIRouter, HTTPException, status

from api.controllers.site_profiles import list_site_profiles
from logger import get_logger
from schemas.site_profiles import SiteProfileInfo
from utils.exceptions import AppError

router = APIRouter(prefix="/site-profiles", tags=["site-profiles"])
logger = get_logger(__name__)


@router.get(
    "",
    response_model=list[SiteProfileInfo],
    summary="List the registered site profiles and the site holding each",
)
async def get_site_profiles() -> list[SiteProfileInfo]:
    try:
        return await list_site_profiles()
    except AppError as e:
        detail = {"error": type(e).__name__, "message": e.message}
        if e.payload:
            detail.update(e.payload)
        raise HTTPException(status_code=e.http_status_code, detail=detail) from e
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred",
        ) from e
