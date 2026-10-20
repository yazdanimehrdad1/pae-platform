"""The ForecastRepository contract, shared by the in-memory fake (unit tests) and Postgres
(tests/integration): every implementation must pass these checks unchanged."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from intelli_gateway.interfaces.forecast_repository import ForecastRepository
from intelli_gateway.schemas.solar_forecast import (
    FetchLogEntry,
    PVArrayInterval,
    PVForecast,
    PVInterval,
    SourceKind,
)

ISSUED = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)
STEP = timedelta(minutes=15)


def forecast(
    issued_at: datetime = ISSUED,
    site_id: int = 1001,
    source_name: str = "open_meteo",
    kind: SourceKind = SourceKind.WEATHER_MODEL,
    with_weather: bool = True,
    fallback_used: bool = False,
) -> PVForecast:
    intervals: list[PVInterval] = []
    for index in range(4):
        start = issued_at + index * STEP
        arrays = (
            (
                PVArrayInterval(
                    array_id=7,
                    poa=500.0 + index,
                    cell_temp_c=40.0,
                    pv_dc_kw=3000.0,
                    pv_ac_kw=2500.0 + index,
                    pv_energy_kwh=(2500.0 + index) / 4,
                ),
                PVArrayInterval(
                    array_id=8,
                    poa=None,
                    cell_temp_c=None,
                    pv_dc_kw=None,
                    pv_ac_kw=100.0,
                    pv_energy_kwh=25.0,
                ),
            )
            if with_weather
            else ()
        )
        intervals.append(
            PVInterval(
                interval_start=start,
                interval_end=start + STEP,
                ghi=800.0 if with_weather else None,
                dni=700.0 if with_weather else None,
                dhi=100.0 if with_weather else None,
                temp_air_c=30.0 if with_weather else None,
                wind_speed_ms=2.0 if with_weather else None,
                cloud_cover_pct=None,
                pv_dc_kw=3000.0 if with_weather else None,
                pv_ac_kw=2600.0 + index,
                pv_energy_kwh=(2600.0 + index) / 4,
                arrays=arrays,
            )
        )
    return PVForecast(
        site_id=site_id,
        source_name=source_name,
        source_kind=kind,
        issued_at=issued_at,
        resolution_minutes=15,
        intervals=tuple(intervals),
        fallback_used=fallback_used,
    )


async def round_trips_a_forecast(repository: ForecastRepository) -> None:
    saved = forecast(fallback_used=True)
    await repository.save(saved)
    assert await repository.latest(1001) == saved
    pv_only = forecast(
        issued_at=ISSUED + timedelta(hours=1),
        site_id=2002,
        source_name="solcast",
        kind=SourceKind.PV_POWER,
        with_weather=False,
    )
    await repository.save(pv_only)
    assert await repository.latest(2002) == pv_only
    assert await repository.latest(3003) is None


async def keeps_history_and_reads_by_issue_time(repository: ForecastRepository) -> None:
    older = forecast(issued_at=ISSUED, source_name="old")
    newer = forecast(issued_at=ISSUED + timedelta(hours=1), source_name="new")
    await repository.save(older)
    await repository.save(newer)
    latest = await repository.latest(1001)
    assert latest is not None and latest.source_name == "new"
    before = await repository.latest(1001, issued_before=ISSUED + timedelta(minutes=30))
    assert before is not None and before.source_name == "old"
    assert await repository.latest(1001, issued_before=ISSUED) is None  # strictly before


async def logs_fetches(repository: ForecastRepository) -> None:
    assert await repository.last_fetch(1001) is None
    ok = FetchLogEntry(site_id=1001, source_name="open_meteo", attempted_at=ISSUED, ok=True)
    failed = FetchLogEntry(
        site_id=1001, source_name="open_meteo", attempted_at=ISSUED + STEP, ok=False, error="503"
    )
    fallback = FetchLogEntry(
        site_id=1001,
        source_name="noaa_hrrr",
        attempted_at=ISSUED + STEP,
        ok=True,
        fallback_used=True,
    )
    for entry in (ok, failed, fallback):
        await repository.log_fetch(entry)
    assert await repository.last_fetch(1001) == fallback
    assert await repository.last_fetch(1001, ok=False) == failed
    assert await repository.last_fetch(1001, ok=True) == fallback
    assert await repository.last_fetch(2002) is None


async def drops_runs_past_retention(repository: ForecastRepository) -> None:
    await repository.save(forecast(issued_at=ISSUED - timedelta(days=100)))
    await repository.save(forecast(issued_at=ISSUED))
    await repository.log_fetch(
        FetchLogEntry(
            site_id=1001, source_name="x", attempted_at=ISSUED - timedelta(days=100), ok=True
        )
    )
    assert await repository.delete_issued_before(ISSUED - timedelta(days=90)) == 1
    latest = await repository.latest(1001, issued_before=ISSUED)
    assert latest is None
    assert await repository.last_fetch(1001) is None


CHECKS: list[Callable[[ForecastRepository], Awaitable[None]]] = [
    round_trips_a_forecast,
    keeps_history_and_reads_by_issue_time,
    logs_fetches,
    drops_runs_past_retention,
]
