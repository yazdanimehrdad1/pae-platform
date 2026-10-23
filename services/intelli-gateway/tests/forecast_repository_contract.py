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
FAR = ISSUED + timedelta(days=30)


def forecast(
    issued_at: datetime = ISSUED,
    site_id: int = 1001,
    source_name: str = "open_meteo",
    kind: SourceKind = SourceKind.WEATHER_MODEL,
    with_weather: bool = True,
    fallback_used: bool = False,
    intervals: int = 4,
) -> PVForecast:
    """A run whose first interval starts at its issue time: 2600 kW, +1 kW per interval."""
    rows: list[PVInterval] = []
    for index in range(intervals):
        start = issued_at + index * STEP
        arrays = (
            (
                PVArrayInterval(array_id=7, pv_ac_kw=2500.0 + index),
                PVArrayInterval(array_id=8, pv_ac_kw=100.0),
            )
            if with_weather
            else ()
        )
        rows.append(
            PVInterval(
                interval_start=start,
                interval_end=start + STEP,
                pv_ac_kw=2600.0 + index,
                ghi=800.0 if with_weather else None,
                temp_air_c=30.0 if with_weather else None,
                wind_speed_ms=2.0 if with_weather else None,
                cloud_cover_pct=40.0 if with_weather else None,
                arrays=arrays,
            )
        )
    return PVForecast(
        site_id=site_id,
        source_name=source_name,
        source_kind=kind,
        issued_at=issued_at,
        resolution_minutes=15,
        intervals=tuple(rows),
        fallback_used=fallback_used,
    )


async def round_trips_a_forecast(repository: ForecastRepository) -> None:
    saved = forecast(fallback_used=True)
    await repository.save(saved)
    assert await repository.as_forecast(1001, ISSUED, FAR) == saved
    pv_only = forecast(
        issued_at=ISSUED + timedelta(hours=1),
        site_id=2002,
        source_name="solcast",
        kind=SourceKind.PV_POWER,
        with_weather=False,
    )
    await repository.save(pv_only)
    assert await repository.as_forecast(2002, ISSUED, FAR) == pv_only
    assert await repository.as_forecast(3003, ISSUED, FAR) is None


async def reads_the_as_forecast_series(repository: ForecastRepository) -> None:
    # Run "old" (issued 10:00) covers 10:00-11:00; run "new" (issued 10:15) covers 10:15-11:15.
    old = forecast(issued_at=ISSUED, source_name="old")
    new = forecast(issued_at=ISSUED + STEP, source_name="new")
    await repository.save(old)
    await repository.save(new)
    await repository.save(forecast(issued_at=ISSUED, site_id=2002, source_name="elsewhere"))

    series = await repository.as_forecast(1001, ISSUED, ISSUED + 5 * STEP)
    assert series is not None
    assert [interval.interval_start for interval in series.intervals] == [
        ISSUED + index * STEP for index in range(5)
    ]
    # 10:00 only "old" was issued by then; from 10:15 the newer "new" run wins.
    assert [interval.pv_ac_kw for interval in series.intervals] == [2600, 2600, 2601, 2602, 2603]
    assert series.intervals[0] == old.intervals[0]  # site row with its weather and arrays
    assert series.intervals[1] == new.intervals[0]
    assert [array.array_id for array in series.intervals[2].arrays] == [7, 8]
    assert series.source_name == "new" and series.issued_at == new.issued_at

    window = await repository.as_forecast(1001, ISSUED + STEP, ISSUED + 3 * STEP)
    assert window is not None
    assert [interval.interval_start for interval in window.intervals] == [
        ISSUED + STEP,
        ISSUED + 2 * STEP,
    ]
    # Nothing was issued before 09:00-10:00 started, and another site's runs don't count.
    assert await repository.as_forecast(1001, ISSUED - 4 * STEP, ISSUED) is None
    assert await repository.as_forecast(3003, ISSUED, ISSUED + STEP) is None


async def prunes_what_a_newer_run_supersedes(repository: ForecastRepository) -> None:
    # Ten refreshes, 15 minutes apart, each forecasting the next 3 hours (12 intervals).
    runs = [
        forecast(issued_at=ISSUED + index * STEP, source_name=f"run{index}", intervals=12)
        for index in range(10)
    ]
    for run in runs:
        await repository.save(run)
    series = await repository.as_forecast(1001, ISSUED, FAR)
    assert series is not None
    # Each past interval keeps the run that was current when it began, the future the newest.
    expected = [run.intervals[0] for run in runs[:-1]] + list(runs[-1].intervals)
    assert list(series.intervals) == expected
    # A run older than everything saved later doesn't remove newer rows.
    await repository.save(forecast(issued_at=ISSUED, source_name="late-old", intervals=1))
    assert await repository.as_forecast(1001, ISSUED, FAR) == series


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
    assert await repository.as_forecast(1001, ISSUED - timedelta(days=101), ISSUED) is None
    kept = await repository.as_forecast(1001, ISSUED, FAR)
    assert kept is not None and kept.issued_at == ISSUED
    assert await repository.last_fetch(1001) is None


CHECKS: list[Callable[[ForecastRepository], Awaitable[None]]] = [
    round_trips_a_forecast,
    reads_the_as_forecast_series,
    prunes_what_a_newer_run_supersedes,
    logs_fetches,
    drops_runs_past_retention,
]
