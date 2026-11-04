"""The logged-in user's own data: preferences, saved Historian trends and notes.

Every route needs a session (never the dev headers), and the user's id comes only from it: an
id in the path that belongs to someone else is a 404, like one that doesn't exist. The one
exception is `PUT trends/order`: an order that isn't exactly your trends is a 422, whether an id
is someone else's or doesn't exist, so it reveals nothing either.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Request, Response, status

from intelli_gateway.api.dependencies import get_current_user
from intelli_gateway.schemas.api_models.requests import (
    NoteCreateRequest,
    NoteUpdateRequest,
    PreferenceRequest,
    TrendOrderRequest,
)
from intelli_gateway.schemas.api_models.responses import ErrorResponse
from intelli_gateway.schemas.user_data import (
    PREFERENCE_KEY_PATTERN,
    Note,
    Preference,
    SavedTrend,
    TrendDefinition,
)
from intelli_gateway.schemas.users import User
from intelli_gateway.user_data.service import UserDataService

router = APIRouter(
    prefix="/v1/me",
    tags=["me"],
    responses={401: {"model": ErrorResponse, "description": "Not logged in"}},
)

PreferenceKey = Annotated[str, Path(pattern=PREFERENCE_KEY_PATTERN)]
Responses = dict[int | str, dict[str, Any]]
NOT_FOUND: Responses = {404: {"model": ErrorResponse, "description": "Not one of yours"}}
TOO_MANY: Responses = {
    422: {"model": ErrorResponse, "description": "Invalid, or over a per-user limit"}
}


def get_user_data(request: Request) -> UserDataService:
    service: UserDataService = request.app.state.services.user_data
    return service


CurrentUser = Annotated[User, Depends(get_current_user)]
Data = Annotated[UserDataService, Depends(get_user_data)]


# --- preferences ---
@router.get("/preferences", response_model=list[Preference], summary="All your preferences")
async def list_preferences(user: CurrentUser, data: Data) -> list[Preference]:
    return await data.list_preferences(user.id)


@router.get(
    "/preferences/{key}", response_model=Preference, responses=NOT_FOUND, summary="One preference"
)
async def get_preference(key: PreferenceKey, user: CurrentUser, data: Data) -> Preference:
    return await data.get_preference(user.id, key)


@router.put(
    "/preferences/{key}",
    response_model=Preference,
    responses=TOO_MANY,
    summary="Set a preference (any JSON value)",
)
async def put_preference(
    key: PreferenceKey, body: PreferenceRequest, user: CurrentUser, data: Data
) -> Preference:
    return await data.put_preference(user.id, key, body.value)


@router.delete(
    "/preferences/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=NOT_FOUND,
    summary="Remove a preference",
)
async def delete_preference(key: PreferenceKey, user: CurrentUser, data: Data) -> Response:
    await data.delete_preference(user.id, key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- saved trends ---
@router.get("/trends", response_model=list[SavedTrend], summary="Your saved trends, in your order")
async def list_trends(user: CurrentUser, data: Data) -> list[SavedTrend]:
    return await data.list_trends(user.id)


@router.post(
    "/trends",
    response_model=SavedTrend,
    status_code=status.HTTP_201_CREATED,
    responses=TOO_MANY,
    summary="Save a trend (added last)",
)
async def create_trend(body: TrendDefinition, user: CurrentUser, data: Data) -> SavedTrend:
    return await data.create_trend(user.id, body)


# Before /trends/{trend_id}, so "order" is never read as an id.
@router.put(
    "/trends/order",
    response_model=list[SavedTrend],
    responses=TOO_MANY,
    summary="Reorder your trends",
)
async def reorder_trends(
    body: TrendOrderRequest, user: CurrentUser, data: Data
) -> list[SavedTrend]:
    return await data.reorder_trends(user.id, body.trend_ids)


@router.put(
    "/trends/{trend_id}",
    response_model=SavedTrend,
    responses=NOT_FOUND,
    summary="Replace a trend's name, points, scale and styles",
)
async def update_trend(
    trend_id: int, body: TrendDefinition, user: CurrentUser, data: Data
) -> SavedTrend:
    return await data.update_trend(user.id, trend_id, body)


@router.delete(
    "/trends/{trend_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=NOT_FOUND,
    summary="Delete a trend",
)
async def delete_trend(trend_id: int, user: CurrentUser, data: Data) -> Response:
    await data.delete_trend(user.id, trend_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- notes ---
@router.get("/notes", response_model=list[Note], summary="Your notes, most recently updated first")
async def list_notes(user: CurrentUser, data: Data) -> list[Note]:
    return await data.list_notes(user.id)


@router.post(
    "/notes",
    response_model=Note,
    status_code=status.HTTP_201_CREATED,
    responses=TOO_MANY,
    summary="Add a note",
)
async def create_note(body: NoteCreateRequest, user: CurrentUser, data: Data) -> Note:
    return await data.create_note(user.id, body.content, body.created_at, body.updated_at)


@router.put("/notes/{note_id}", response_model=Note, responses=NOT_FOUND, summary="Edit a note")
async def update_note(note_id: int, body: NoteUpdateRequest, user: CurrentUser, data: Data) -> Note:
    return await data.update_note(user.id, note_id, body.content)


@router.delete(
    "/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=NOT_FOUND,
    summary="Delete a note",
)
async def delete_note(note_id: int, user: CurrentUser, data: Data) -> Response:
    await data.delete_note(user.id, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
