-- Migration: 017_create_pv_array_configs
-- The physical PV array behind a PV or INVERTER device (orientation, ratings, losses), read by the PV forecast.

CREATE TABLE pv_array_configs (
    device_id INTEGER NOT NULL
        CONSTRAINT pv_array_configs_pkey PRIMARY KEY
        CONSTRAINT fk_pv_array_configs_device REFERENCES devices (device_id) ON DELETE CASCADE,
    tilt_deg DOUBLE PRECISION NOT NULL
        CONSTRAINT ck_pv_array_configs_tilt CHECK (tilt_deg >= 0 AND tilt_deg <= 90),
    azimuth_deg DOUBLE PRECISION NOT NULL
        CONSTRAINT ck_pv_array_configs_azimuth CHECK (azimuth_deg >= 0 AND azimuth_deg < 360),
    dc_capacity_kw DOUBLE PRECISION NOT NULL
        CONSTRAINT ck_pv_array_configs_dc_capacity CHECK (dc_capacity_kw > 0),
    ac_capacity_kw DOUBLE PRECISION NOT NULL
        CONSTRAINT ck_pv_array_configs_ac_capacity CHECK (ac_capacity_kw > 0),
    system_loss_pct DOUBLE PRECISION NOT NULL DEFAULT 14
        CONSTRAINT ck_pv_array_configs_system_loss CHECK (system_loss_pct >= 0 AND system_loss_pct < 100),
    temp_coefficient_pct_per_c DOUBLE PRECISION NOT NULL DEFAULT -0.35
        CONSTRAINT ck_pv_array_configs_temp_coefficient CHECK (temp_coefficient_pct_per_c >= -2 AND temp_coefficient_pct_per_c <= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE pv_array_configs IS 'PV array behind a PV or INVERTER device (at most one per device); the API enforces the device type';
COMMENT ON COLUMN pv_array_configs.device_id IS 'The PV or INVERTER device; deleting the device deletes its array config';
COMMENT ON COLUMN pv_array_configs.tilt_deg IS 'Module tilt from horizontal, degrees (0 = flat, 90 = vertical)';
COMMENT ON COLUMN pv_array_configs.azimuth_deg IS 'Direction the modules face, degrees clockwise from north (180 = south)';
COMMENT ON COLUMN pv_array_configs.dc_capacity_kw IS 'DC nameplate of the array, kW (kWp)';
COMMENT ON COLUMN pv_array_configs.ac_capacity_kw IS 'AC limit of the inverter(s) feeding this array, kW; output is clipped here';
COMMENT ON COLUMN pv_array_configs.system_loss_pct IS 'Lumped DC/AC system losses (soiling, wiring, mismatch, inverter), percent';
COMMENT ON COLUMN pv_array_configs.temp_coefficient_pct_per_c IS 'Module power temperature coefficient, percent per degC (negative)';
COMMENT ON COLUMN pv_array_configs.created_at IS 'When the config was first saved';
COMMENT ON COLUMN pv_array_configs.updated_at IS 'When the config was last saved';
