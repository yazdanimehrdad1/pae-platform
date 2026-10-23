-- Migration: 002_slim_forecasts
-- Store only what is served: AC power (site and per array) and the weather (GHI, air temperature,
-- wind, cloud cover). DNI, DHI, plane-of-array irradiance, cell temperature, DC power and energy
-- are the PV model's internals and are no longer kept.

ALTER TABLE forecast_intervals
    DROP COLUMN dni,
    DROP COLUMN dhi,
    DROP COLUMN poa,
    DROP COLUMN cell_temp_c,
    DROP COLUMN pv_dc_kw,
    DROP COLUMN pv_energy_kwh;

COMMENT ON TABLE forecast_runs IS 'One PV forecast per site refresh; a newer run supersedes (deletes) the older rows for the intervals it covers, so each interval keeps the forecast current when it began';
COMMENT ON TABLE forecast_intervals IS 'Intervals: array_id NULL = site total with the weather (GHI, air temperature, wind, cloud cover), else one PV array''s AC power';
