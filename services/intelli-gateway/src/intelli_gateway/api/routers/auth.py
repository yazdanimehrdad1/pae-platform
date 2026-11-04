"""Login, logout and the logged-in user. The session token travels only in the HttpOnly cookie."""

from fastapi import APIRouter, Depends, Request, Response, status

from intelli_gateway.api.dependencies import (
    SESSION_COOKIE,
    clear_session_cookie,
    get_auth_service,
    get_current_user,
    get_settings,
    set_session_cookie,
)
from intelli_gateway.auth.service import AuthService
from intelli_gateway.config import Settings
from intelli_gateway.schemas.api_models.requests import LoginRequest, PasswordChangeRequest
from intelli_gateway.schemas.api_models.responses import ErrorResponse, MeResponse
from intelli_gateway.schemas.users import User

router = APIRouter(prefix="/v1", tags=["auth"])


def _me(user: User) -> MeResponse:
    return MeResponse(id=user.id, email=user.email, display_name=user.display_name, role=user.role)


@router.post(
    "/auth/login",
    response_model=MeResponse,
    responses={401: {"model": ErrorResponse, "description": "Wrong email or password"}},
    summary="Log in: sets the session cookie",
)
async def login(
    body: LoginRequest,
    response: Response,
    settings: Settings = Depends(get_settings),
    auth: AuthService = Depends(get_auth_service),
) -> MeResponse:
    user, token = await auth.login(body.email, body.password)
    set_session_cookie(response, settings, token, auth.session_ttl)
    return _me(user)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Log out: ends the session and clears the cookie",
)
async def logout(
    request: Request,
    settings: Settings = Depends(get_settings),
    auth: AuthService = Depends(get_auth_service),
) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await auth.logout(token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response, settings)
    return response


@router.get(
    "/me",
    response_model=MeResponse,
    responses={401: {"model": ErrorResponse, "description": "Not logged in"}},
    summary="The logged-in user",
)
async def me(user: User = Depends(get_current_user)) -> MeResponse:
    return _me(user)


@router.put(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        401: {"model": ErrorResponse, "description": "Not logged in"},
        403: {"model": ErrorResponse, "description": "The current password is wrong"},
    },
    summary="Change your own password (your other sessions end; this one stays)",
)
async def change_password(
    body: PasswordChangeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    auth: AuthService = Depends(get_auth_service),
) -> Response:
    token = request.cookies.get(SESSION_COOKIE, "")
    await auth.change_own_password(user.id, token, body.current_password, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
