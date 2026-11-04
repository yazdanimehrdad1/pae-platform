"""FastAPI dependencies: who is asking (the session cookie), access checks, the wired services."""

from datetime import timedelta

from fastapi import Header, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncEngine

from intelli_gateway.agent.service import GatewayService
from intelli_gateway.auth.service import AuthService
from intelli_gateway.config import Settings
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.users import User
from intelli_gateway.solar_forecast.service import ForecastService
from intelli_gateway.utils.exceptions import ForbiddenError, UnauthorizedError
from intelli_gateway.utils.logger import request_id_var

DEV_USER_ID = "dev-user"
# The session cookie's name. Fixed: web-plusdas's nginx reads it by this name for its login check.
SESSION_COOKIE = "plusdas_session"


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_auth_service(request: Request) -> AuthService:
    service: AuthService = request.app.state.services.auth
    return service


def set_session_cookie(
    response: Response, settings: Settings, token: str, max_age: timedelta
) -> None:
    """HttpOnly (scripts never see the token), SameSite=Lax, path / (nginx's auth check on the
    other services' routes reads it too), Secure once the site is on HTTPS."""
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(max_age.total_seconds()),
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )


async def get_current_user(request: Request, response: Response) -> User:
    """The user of the session cookie; 401 without a valid session. Re-issues the cookie when the
    request slid the session's expiry forward. Never falls back to the dev headers: per-user
    routes always need a real login."""
    settings = get_settings(request)
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise UnauthorizedError("not logged in")
    authenticated = await get_auth_service(request).authenticate(token)
    if authenticated.renewed_until is not None:
        set_session_cookie(response, settings, token, get_auth_service(request).session_ttl)
    return authenticated.user


def _split(header: str | None) -> list[str]:
    return [part.strip() for part in (header or "").split(",") if part.strip()]


async def get_request_context(
    request: Request,
    response: Response,
    x_user_id: str | None = Header(default=None, description="Dev auth only: user id."),
    x_roles: str | None = Header(default=None, description="Dev auth only: comma-separated roles."),
    x_site_ids: str | None = Header(
        default=None, description="Dev auth only: comma-separated site ids the user may access."
    ),
) -> RequestContext:
    """Who is asking: the logged-in user. With AUTH_DEV_HEADERS on, a request without a session
    cookie is taken from the X-* headers instead (or the dev user). Tools and the agent loop only
    see RequestContext."""
    settings = get_settings(request)
    if request.cookies.get(SESSION_COOKIE) or not settings.auth_dev_headers:
        user = await get_current_user(request, response)
        # TODO(auth): per-site grants; until then a user may access every site.
        return RequestContext(
            user_id=str(user.id),
            roles=frozenset({user.role}),
            site_ids=None,
            request_id=request_id_var.get() or "-",
        )
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
