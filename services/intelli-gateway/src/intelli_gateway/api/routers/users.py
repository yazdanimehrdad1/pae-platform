"""Account management for admins: list users, add one, change a role or name, disable, and reset
a password. There is no self-signup; the first admin of an environment comes from its secret
(BOOTSTRAP_ADMIN_PASSWORD), and that admin adds everyone else here."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status

from intelli_gateway.api.dependencies import get_auth_service, require_admin
from intelli_gateway.auth.service import AuthService
from intelli_gateway.schemas.api_models.requests import (
    PasswordResetRequest,
    UserCreateRequest,
    UserUpdateRequest,
)
from intelli_gateway.schemas.api_models.responses import ErrorResponse, UserResponse
from intelli_gateway.schemas.users import User

Responses = dict[int | str, dict[str, Any]]
router = APIRouter(
    prefix="/v1/users",
    tags=["users"],
    responses={
        401: {"model": ErrorResponse, "description": "Not logged in"},
        403: {"model": ErrorResponse, "description": "Not an admin"},
    },
)
NOT_FOUND: Responses = {404: {"model": ErrorResponse, "description": "No such user"}}
Admin = Annotated[User, Depends(require_admin)]
Auth = Annotated[AuthService, Depends(get_auth_service)]


def _response(user: User) -> UserResponse:
    return UserResponse.model_validate(user.model_dump(include=set(UserResponse.model_fields)))


@router.get("", response_model=list[UserResponse], summary="Every account, by email")
async def list_users(admin: Admin, auth: Auth) -> list[UserResponse]:
    del admin
    return [_response(user) for user in await auth.list_users()]


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "The email is taken"}},
    summary="Add an account",
)
async def create_user(body: UserCreateRequest, admin: Admin, auth: Auth) -> UserResponse:
    del admin
    return _response(
        await auth.create_user(body.email, body.display_name, body.role, body.password)
    )


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    responses={
        **NOT_FOUND,
        422: {"model": ErrorResponse, "description": "e.g. demoting or disabling yourself"},
    },
    summary="Change an account's name, role, or disabled state",
)
async def update_user(
    user_id: int, body: UserUpdateRequest, admin: Admin, auth: Auth
) -> UserResponse:
    return _response(
        await auth.update_user(
            admin,
            user_id,
            display_name=body.display_name,
            role=body.role,
            disabled=body.disabled,
        )
    )


@router.put(
    "/{user_id}/password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=NOT_FOUND,
    summary="Set an account's password (ends its sessions)",
)
async def reset_password(
    user_id: int, body: PasswordResetRequest, admin: Admin, auth: Auth
) -> Response:
    del admin
    await auth.reset_password(user_id, body.password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
