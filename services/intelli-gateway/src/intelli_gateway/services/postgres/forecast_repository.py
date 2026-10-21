"""PostgresForecastRepository: PV forecasts and the fetch log in this service's Postgres
(SQLAlchemy 2 Core over asyncpg). One run row per refresh; its intervals are one site-total row
(array_id NULL, carrying the weather) plus one row per PV array."""

from collections import defaultdict
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    delete,
    insert,
    select,
)
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine

from intelli_gateway.schemas.solar_forecast import (
    FetchLogEntry,
    PVArrayInterval,
    PVForecast,
    PVInterval,
    SourceKind,
)

metadata = MetaData()
runs_table = Table(
    "forecast_runs",
    metadata,
    Column("id", BigInteger(), primary_key=True, autoincrement=True),
    Column("site_id", Integer(), nullable=False),
    Column("source_name", Text(), nullable=False),
    Column("source_kind", Text(), nullable=False),
    Column("issued_at", DateTime(timezone=True), nullable=False),
    Column("resolution_minutes", Integer(), nullable=False),
    Column("fallback_used", Boolean(), nullable=False),
)
intervals_table = Table(
    "forecast_intervals",
    metadata,
    Column("run_id", BigInteger(), ForeignKey("forecast_runs.id"), nullable=False),
    Column("site_id", Integer(), nullable=False),
    Column("array_id", Integer()),
    Column("issued_at", DateTime(timezone=True), nullable=False),
    Column("interval_start", DateTime(timezone=True), nullable=False),
    Column("interval_end", DateTime(timezone=True), nullable=False),
    Column("ghi", Float()),
    Column("dni", Float()),
    Column("dhi", Float()),
    Column("temp_air_c", Float()),
    Column("wind_speed_ms", Float()),
    Column("cloud_cover_pct", Float()),
    Column("poa", Float()),
    Column("cell_temp_c", Float()),
    Column("pv_dc_kw", Float()),
    Column("pv_ac_kw", Float(), nullable=False),
    Column("pv_energy_kwh", Float(), nullable=False),
)
fetch_log_table = Table(
    "forecast_fetch_log",
    metadata,
    Column("id", BigInteger(), primary_key=True, autoincrement=True),
    Column("site_id", Integer(), nullable=False),
    Column("source_name", Text(), nullable=False),
    Column("attempted_at", DateTime(timezone=True), nullable=False),
    Column("ok", Boolean(), nullable=False),
    Column("fallback_used", Boolean(), nullable=False),
    Column("error", Text()),
)

_WEATHER_COLUMNS = ("ghi", "dni", "dhi", "temp_air_c", "wind_speed_ms", "cloud_cover_pct")


def _interval_rows(run_id: int, forecast: PVForecast) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for interval in forecast.intervals:
        common: dict[str, object] = {
            "run_id": run_id,
            "site_id": forecast.site_id,
            "issued_at": forecast.issued_at,
            "interval_start": interval.interval_start,
            "interval_end": interval.interval_end,
        }
        rows.append(
            common
            | {column: getattr(interval, column) for column in _WEATHER_COLUMNS}
            | {
                "array_id": None,
                "poa": None,
                "cell_temp_c": None,
                "pv_dc_kw": interval.pv_dc_kw,
                "pv_ac_kw": interval.pv_ac_kw,
                "pv_energy_kwh": interval.pv_energy_kwh,
            }
        )
        for array in interval.arrays:
            rows.append(
                common
                | dict.fromkeys(_WEATHER_COLUMNS)
                | {
                    "array_id": array.array_id,
                    "poa": array.poa,
                    "cell_temp_c": array.cell_temp_c,
                    "pv_dc_kw": array.pv_dc_kw,
                    "pv_ac_kw": array.pv_ac_kw,
                    "pv_energy_kwh": array.pv_energy_kwh,
                }
            )
    return rows


def _to_forecast(run: RowMapping, rows: list[RowMapping]) -> PVForecast:
    arrays_by_start: defaultdict[datetime, list[PVArrayInterval]] = defaultdict(list)
    totals: list[RowMapping] = []
    for row in rows:
        if row["array_id"] is None:
            totals.append(row)
        else:
            arrays_by_start[row["interval_start"]].append(
                PVArrayInterval(
                    array_id=row["array_id"],
                    poa=row["poa"],
                    cell_temp_c=row["cell_temp_c"],
                    pv_dc_kw=row["pv_dc_kw"],
                    pv_ac_kw=row["pv_ac_kw"],
                    pv_energy_kwh=row["pv_energy_kwh"],
                )
            )
    return PVForecast(
        site_id=run["site_id"],
        source_name=run["source_name"],
        source_kind=SourceKind(run["source_kind"]),
        issued_at=run["issued_at"],
        resolution_minutes=run["resolution_minutes"],
        fallback_used=run["fallback_used"],
        intervals=tuple(
            PVInterval(
                interval_start=row["interval_start"],
                interval_end=row["interval_end"],
                ghi=row["ghi"],
                dni=row["dni"],
                dhi=row["dhi"],
                temp_air_c=row["temp_air_c"],
                wind_speed_ms=row["wind_speed_ms"],
                cloud_cover_pct=row["cloud_cover_pct"],
                pv_dc_kw=row["pv_dc_kw"],
                pv_ac_kw=row["pv_ac_kw"],
                pv_energy_kwh=row["pv_energy_kwh"],
                arrays=tuple(
                    sorted(arrays_by_start[row["interval_start"]], key=lambda item: item.array_id)
                ),
            )
            for row in totals
        ),
    )


class PostgresForecastRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, forecast: PVForecast) -> None:
        async with self._engine.begin() as connection:
            run_id = (
                await connection.execute(
                    insert(runs_table)
                    .values(
                        site_id=forecast.site_id,
                        source_name=forecast.source_name,
                        source_kind=forecast.source_kind.value,
                        issued_at=forecast.issued_at,
                        resolution_minutes=forecast.resolution_minutes,
                        fallback_used=forecast.fallback_used,
                    )
                    .returning(runs_table.c.id)
                )
            ).scalar_one()
            rows = _interval_rows(int(run_id), forecast)
            if rows:
                await connection.execute(insert(intervals_table), rows)

    async def latest(self, site_id: int) -> PVForecast | None:
        query = (
            select(runs_table)
            .where(runs_table.c.site_id == site_id)
            .order_by(runs_table.c.issued_at.desc(), runs_table.c.id.desc())
            .limit(1)
        )
        async with self._engine.connect() as connection:
            run = (await connection.execute(query)).mappings().first()
            if run is None:
                return None
            rows = (
                (
                    await connection.execute(
                        select(intervals_table)
                        .where(intervals_table.c.run_id == run["id"])
                        .order_by(intervals_table.c.interval_start, intervals_table.c.array_id)
                    )
                )
                .mappings()
                .all()
            )
        return _to_forecast(run, list(rows))

    async def log_fetch(self, entry: FetchLogEntry) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(insert(fetch_log_table).values(**entry.model_dump()))

    async def last_fetch(self, site_id: int, ok: bool | None = None) -> FetchLogEntry | None:
        query = select(fetch_log_table).where(fetch_log_table.c.site_id == site_id)
        if ok is not None:
            query = query.where(fetch_log_table.c.ok == ok)
        query = query.order_by(
            fetch_log_table.c.attempted_at.desc(), fetch_log_table.c.id.desc()
        ).limit(1)
        async with self._engine.connect() as connection:
            row = (await connection.execute(query)).mappings().first()
        if row is None:
            return None
        return FetchLogEntry.model_validate({key: row[key] for key in FetchLogEntry.model_fields})

    async def delete_issued_before(self, cutoff: datetime) -> int:
        async with self._engine.begin() as connection:
            deleted = await connection.execute(
                delete(runs_table).where(runs_table.c.issued_at < cutoff)
            )
            await connection.execute(
                delete(fetch_log_table).where(fetch_log_table.c.attempted_at < cutoff)
            )
        return deleted.rowcount

    async def aclose(self) -> None:
        await self._engine.dispose()
