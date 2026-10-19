"""HTTP client for backend-ot's read-only API. Every request this service makes to backend-ot
goes through BackendOtClient.

Each call has a timeout and is retried (tenacity) on connection errors, timeouts and 5xx; 4xx
is not retried. Responses are validated against the strict models in schemas/backend_ot/.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import TypeVar

import httpx
from pydantic import TypeAdapter, ValidationError
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from intelli_gateway.schemas.backend_ot.responses import (
    AlarmEventResponse,
    AlarmSnapshotResponse,
    DeviceWithPoints,
    LatestResponse,
    SiteHealthResponse,
    SiteResponse,
    SiteSldResponse,
    TimeseriesResponse,
)
from intelli_gateway.utils.exceptions import BackendOtError

T = TypeVar("T")
QueryValue = str | int | float | bool
Query = dict[str, QueryValue]

_SITES = TypeAdapter(list[SiteResponse])
_SITE = TypeAdapter(SiteResponse)
_DEVICES = TypeAdapter(list[DeviceWithPoints])
_SLD = TypeAdapter(SiteSldResponse)
_LATEST = TypeAdapter(LatestResponse)
_TIMESERIES = TypeAdapter(TimeseriesResponse)
_SNAPSHOT = TypeAdapter(AlarmSnapshotResponse)
_EVENTS = TypeAdapter(list[AlarmEventResponse])
_HEALTH = TypeAdapter(SiteHealthResponse)
# backend-ot clamps `max_points` to this range.
MAX_POINTS_RANGE = (100, 5000)


def _is_retryable(error: BaseException) -> bool:
    if isinstance(error, httpx.TransportError):  # connect/read errors and timeouts
        return True
    return isinstance(error, httpx.HTTPStatusError) and error.response.status_code >= 500


def _parse(adapter: TypeAdapter[T], body: bytes) -> T:
    try:
        return adapter.validate_json(body)
    except ValidationError as error:
        raise BackendOtError(
            f"backend-ot response does not match the expected shape "
            f"({error.error_count()} problems; contract drift?)"
        ) from error


def _ids(point_ids: Sequence[int]) -> str:
    return ",".join(str(point_id) for point_id in point_ids)


class BackendOtClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float,
        attempts: int,
        transport: httpx.AsyncBaseTransport | None = None,
        max_wait_s: float = 4.0,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=httpx.Timeout(timeout_s), transport=transport
        )
        self._attempts = attempts
        self._max_wait_s = max_wait_s

    # --- sites and catalog ---

    async def list_sites(self) -> list[SiteResponse]:
        return _parse(_SITES, await self._get("/api/sites"))

    async def get_site(self, site_id: int) -> SiteResponse | None:
        body = await self._get(f"/api/sites/{site_id}", allow_404=True)
        return _parse(_SITE, body) if body else None

    async def list_devices(self, site_id: int) -> list[DeviceWithPoints]:
        return _parse(_DEVICES, await self._get(f"/api/devices/site/{site_id}/devices"))

    async def get_sld(self, site_id: int) -> SiteSldResponse | None:
        """None when the site has no single-line diagram yet."""
        body = await self._get(f"/api/sites/{site_id}/sld", allow_404=True)
        return _parse(_SLD, body) if body else None

    # --- readings ---

    async def latest(
        self, site_id: int, device_id: int, point_ids: Sequence[int] | None = None
    ) -> LatestResponse:
        query: Query = {"translate": True}
        if point_ids:
            query["point_ids"] = _ids(point_ids)
        body = await self._get(
            f"/api/device-point-readings/site/{site_id}/device/{device_id}/latest", query
        )
        return _parse(_LATEST, body)

    async def timeseries(
        self,
        site_id: int,
        device_id: int,
        point_ids: Sequence[int],
        start: datetime,
        end: datetime,
        max_points: int | None = None,
    ) -> TimeseriesResponse:
        query: Query = {
            "point_ids": _ids(point_ids),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "translate": True,
        }
        if max_points is not None:
            low, high = MAX_POINTS_RANGE
            query["max_points"] = min(max(max_points, low), high)
        body = await self._get(
            f"/api/device-point-readings/timeseries/site/{site_id}/device/{device_id}", query
        )
        return _parse(_TIMESERIES, body)

    # --- alarms ---

    async def alarm_snapshot(self, site_id: int) -> AlarmSnapshotResponse:
        body = await self._get(f"/api/alarms/site/{site_id}/snapshot")
        return _parse(_SNAPSHOT, body)

    async def alarm_events(
        self, site_id: int, start: datetime, end: datetime, device_id: int | None = None
    ) -> list[AlarmEventResponse]:
        query: Query = {"start_time": start.isoformat(), "end_time": end.isoformat()}
        if device_id is not None:
            query["device_id"] = device_id
        return _parse(_EVENTS, await self._get(f"/api/alarms/site/{site_id}/events", query))

    async def site_health(self, site_id: int) -> SiteHealthResponse:
        """Active ALARM-class points (non-zero alarm words, fault codes) per device."""
        return _parse(_HEALTH, await self._get(f"/api/sites/{site_id}/health"))

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- transport ---

    async def _get(self, path: str, query: Query | None = None, allow_404: bool = False) -> bytes:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._attempts),
                wait=wait_exponential(multiplier=0.5, max=self._max_wait_s),
                retry=retry_if_exception(_is_retryable),
                reraise=True,
            ):
                with attempt:
                    response = await self._client.get(path, params=query)
                    if allow_404 and response.status_code == 404:
                        return b""
                    response.raise_for_status()
                    return response.content
        except httpx.HTTPStatusError as error:
            raise BackendOtError(
                f"backend-ot returned {error.response.status_code} for {path}"
            ) from error
        except httpx.HTTPError as error:
            raise BackendOtError(f"backend-ot unreachable ({type(error).__name__})") from error
        raise BackendOtError("backend-ot request failed")  # unreachable: reraise=True
