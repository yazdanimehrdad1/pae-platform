"""Compute and store the values of each site's profile virtual points (job `profile_point_compute`).

Runs every poll interval, separately from polling, and reads only the database. For each point a
site's profile declares (SiteVirtualPoint), in declaration order:
1. the window is (computed_until, now - settle]: settle gives every device of the latest poll time
   to store its readings. A point never computed starts `backfill` before now (with no backfill,
   its first run only records now - settle as computed_until); a window longer than
   PROFILE_POINT_MAX_WINDOW_SECONDS is cut, and the rest is caught up by the next runs;
2. its `compute` runs with a VirtualPointContext of the window (cancelled after
   PROFILE_POINT_TIMEOUT_SECONDS);
3. the values inside the window are upserted into device_points_readings and computed_until moves
   to the window's end, in one transaction.
A point that fails keeps its computed_until, so the next run retries the same window. One point
failing doesn't stop the others.
"""

import asyncio
from datetime import datetime, timedelta

import db.devices as devices_db
import db.sites as sites_db
from config import settings
from db.profile_points import get_computed_until, get_profile_points, store_computed_values
from logger import get_logger
from schemas.internal_models import TimestampedValue
from schemas.site_profiles import VirtualPointContext
from site_profiles.profile_registry import SITE_PROFILES_BY_KEY

logger = get_logger(__name__)


def compute_window(
    computed_until: datetime | None, now: datetime, backfill: timedelta, settle: timedelta, max_window: timedelta
) -> tuple[datetime, datetime] | None:
    """Pure: the (start, end] window a run computes, or None when there is nothing new yet."""
    latest_settled = now - settle
    start = computed_until if computed_until is not None else latest_settled - backfill
    end = min(latest_settled, start + max_window)
    return (start, end) if end > start else None


def values_in_window(values: list[TimestampedValue], start: datetime, end: datetime) -> list[TimestampedValue]:
    """Pure: the values in (start, end], one per timestamp (the last one returned wins)."""
    by_time = {value.time: value for value in values if start < value.time <= end}
    return sorted(by_time.values(), key=lambda value: value.time)


async def compute_site_profile_points(site_id: int, now: datetime) -> None:
    """One compute cycle for a site."""
    site = await sites_db.get_site_by_id(site_id)
    profile = SITE_PROFILES_BY_KEY.get(site.profile) if site is not None and site.profile is not None else None
    if site is None or profile is None or not profile.virtual_points:
        return
    points_by_key = {
        (point.device_id, point.profile_point_key): point for point in await get_profile_points(site_id)
    }
    computed_until = await get_computed_until([point.id for point in points_by_key.values()])
    devices = await devices_db.get_all_devices(site_id)
    devices_by_name = {device.name: device for device in devices}

    for declared in profile.virtual_points:
        device = devices_by_name.get(declared.device_name)
        point = points_by_key.get((device.device_id, declared.key)) if device is not None else None
        if device is None or point is None:
            continue  # not synced yet (helpers.profile_points.sync logs why)
        settle = timedelta(seconds=settings.profile_point_settle_seconds)
        point_computed_until = computed_until.get(point.id)
        window = compute_window(
            point_computed_until,
            now,
            declared.backfill,
            settle,
            timedelta(seconds=settings.profile_point_max_window_seconds),
        )
        if window is None:
            if point_computed_until is None:
                # A new point without backfill: start its clock, so the next run computes from here.
                await store_computed_values(point, [], now - settle)
            continue
        start, end = window
        context = VirtualPointContext(site=site, devices=devices, device=device, start=start, end=end)
        try:
            values = await asyncio.wait_for(declared.compute(context), settings.profile_point_timeout_seconds)
            await store_computed_values(point, values_in_window(values, start, end), end)
        except Exception as error:
            logger.error(
                "site %s: profile virtual point '%s' failed for (%s, %s]: %s",
                site_id, declared.key, start.isoformat(), end.isoformat(), error, exc_info=True,
            )


async def compute_all_sites_profile_points(now: datetime) -> None:
    """One compute cycle for every site. One site failing is logged and doesn't stop the others."""
    for site in await sites_db.get_all_sites():
        try:
            await compute_site_profile_points(site.site_id, now)
        except Exception as error:
            logger.error("site %s: profile virtual point computation failed: %s", site.site_id, error, exc_info=True)
