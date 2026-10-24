"""FastAPI dependencies: the auth placeholder, access checks and the wired services."""

from fastapi import Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncEngine

from intelli_gateway.agent.service import GatewayService
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.solar_forecast.service import ForecastService
from intelli_gateway.utils.exceptions import ForbiddenError
from intelli_gateway.utils.logger import request_id_var

DEV_USER_ID = "dev-user"


def _split(header: str | None) -> list[str]:
    return [part.strip() for part in (header or "").split(",") if part.strip()]


def get_request_context(
    x_user_id: str | None = Header(default=None, description="Dev auth: user id."),
    x_roles: str | None = Header(default=None, description="Dev auth: comma-separated roles."),
    x_site_ids: str | None = Header(
        default=None, description="Dev auth: comma-separated site ids the user may access."
    ),
) -> RequestContext:
    # TODO(auth): replace with OIDC/JWT validation (Keycloak or the company identity provider):
    # take user, roles and site access from the validated token. Tools and the agent loop only
    # see RequestContext, so they do not change.
    site_ids: frozenset[int] | None = None
    if x_site_ids is not None:
        try:
            site_ids = frozenset(int(part) for part in _split(x_site_ids))
        except ValueError as error:
            raise HTTPException(
                status_code=400, detail="X-Site-Ids must be comma-separated integers"
            ) from error
    return RequestContext(
        user_id=x_user_id or DEV_USER_ID,
        roles=frozenset(_split(x_roles) or ["engineer"]),
        site_ids=site_ids,
        request_id=request_id_var.get() or "-",
    )


def get_service(request: Request) -> GatewayService:
    service: GatewayService = request.app.state.services.gateway
    return service


def get_forecast_service(request: Request) -> ForecastService:
    service: ForecastService = request.app.state.services.forecast
    return service


def get_database(request: Request) -> AsyncEngine | None:
    """This service's own Postgres engine, or None when DATABASE_URL is unset."""
    database: AsyncEngine | None = request.app.state.services.database
    return database


def require_site_access(ctx: RequestContext, site_id: int) -> None:
    if not ctx.can_access_site(site_id):
        raise ForbiddenError("no access to this site")


def require_role(ctx: RequestContext, role: str) -> None:
    if role not in ctx.roles:
        raise ForbiddenError(f"requires the {role} role")
