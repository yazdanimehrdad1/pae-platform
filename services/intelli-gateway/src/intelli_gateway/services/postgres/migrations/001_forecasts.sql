-- Migration: 001_forecasts
-- PV forecasts: one run per refresh of a site (history kept, never overwritten), its intervals
-- (site totals plus a per-array breakdown), and the fetch log behind /api/v1/forecast/health.

CREATE TABLE forecast_runs (
    id BIGSERIAL CONSTRAINT forecast_runs_pkey PRIMARY KEY,
    site_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    source_kind TEXT NOT NULL
        CONSTRAINT ck_forecast_runs_source_kind CHECK (source_kind IN ('weather_model', 'pv_power')),
    issued_at TIMESTAMPTZ NOT NULL,
    resolution_minutes INTEGER NOT NULL
        CONSTRAINT ck_forecast_runs_resolution CHECK (resolution_minutes > 0),
    fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_forecast_runs_site_issued ON forecast_runs (site_id, issued_at DESC);

CREATE TABLE forecast_intervals (
    run_id BIGINT NOT NULL
        CONSTRAINT fk_forecast_intervals_run REFERENCES forecast_runs (id) ON DELETE CASCADE,
    site_id INTEGER NOT NULL,
    array_id INTEGER,
    issued_at TIMESTAMPTZ NOT NULL,
    interval_start TIMESTAMPTZ NOT NULL,
    interval_end TIMESTAMPTZ NOT NULL,
    ghi DOUBLE PRECISION,
    dni DOUBLE PRECISION,
    dhi DOUBLE PRECISION,
    temp_air_c DOUBLE PRECISION,
    wind_speed_ms DOUBLE PRECISION,
    cloud_cover_pct DOUBLE PRECISION,
    poa DOUBLE PRECISION,
    cell_temp_c DOUBLE PRECISION,
    pv_dc_kw DOUBLE PRECISION,
    pv_ac_kw DOUBLE PRECISION NOT NULL,
    pv_energy_kwh DOUBLE PRECISION NOT NULL,
    CONSTRAINT ck_forecast_intervals_ordered CHECK (interval_end > interval_start)
);

CREATE UNIQUE INDEX uq_forecast_intervals_run_array_start
    ON forecast_intervals (run_id, COALESCE(array_id, -1), interval_start);
CREATE INDEX idx_forecast_intervals_site_start_issued
    ON forecast_intervals (site_id, interval_start, issued_at);

CREATE TABLE forecast_fetch_log (
    id BIGSERIAL CONSTRAINT forecast_fetch_log_pkey PRIMARY KEY,
    site_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL,
    ok BOOLEAN NOT NULL,
    fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
    error TEXT
);

CREATE INDEX idx_forecast_fetch_log_site_attempted ON forecast_fetch_log (site_id, attempted_at DESC);

COMMENT ON TABLE forecast_runs IS 'One PV forecast per site refresh, from one source; kept for backtesting until retention';
COMMENT ON COLUMN forecast_runs.site_id IS 'backend-ot site id';
COMMENT ON COLUMN forecast_runs.source_name IS 'The source that produced it (open_meteo, solcast, ...)';
COMMENT ON COLUMN forecast_runs.source_kind IS 'weather_model: weather API plus this service PV model; pv_power: an API that predicts PV power';
COMMENT ON COLUMN forecast_runs.issued_at IS 'When the forecast was fetched (UTC)';
COMMENT ON COLUMN forecast_runs.fallback_used IS 'A fallback source produced it because the primary failed';
COMMENT ON TABLE forecast_intervals IS 'Intervals of a run: array_id NULL = site total (with the weather), else one PV array';
COMMENT ON COLUMN forecast_intervals.array_id IS 'backend-ot device id of the PV array; NULL for the site total row';
COMMENT ON COLUMN forecast_intervals.interval_start IS 'Start of [interval_start, interval_end); values are means over it, energy its sum';
COMMENT ON COLUMN forecast_intervals.poa IS 'Plane-of-array irradiance, W/m2 (array rows)';
COMMENT ON COLUMN forecast_intervals.pv_ac_kw IS 'Mean AC power over the interval, kW';
COMMENT ON COLUMN forecast_intervals.pv_energy_kwh IS 'AC energy over the interval, kWh';
COMMENT ON TABLE forecast_fetch_log IS 'Every refresh attempt per site and source: success or the error';
