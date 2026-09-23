-- Migration: 004_create_device_points_readings_table
-- Baseline (squashed 2026-09-22 from migrations 001-049): time-series readings per device point.
-- Plain Postgres table (no hypertable).

CREATE TABLE device_points_readings (
    "timestamp" TIMESTAMPTZ NOT NULL,
    site_id INTEGER NOT NULL
        CONSTRAINT fk_device_points_readings_site REFERENCES sites (id) ON DELETE CASCADE,
    device_id INTEGER NOT NULL
        CONSTRAINT fk_device_points_readings_device REFERENCES devices (device_id) ON DELETE CASCADE,
    device_point_id INTEGER NOT NULL
        CONSTRAINT fk_device_points_readings_device_point REFERENCES device_points (id) ON DELETE CASCADE,
    raw_value DOUBLE PRECISION,
    derived_value DOUBLE PRECISION,
    CONSTRAINT device_points_readings_pkey PRIMARY KEY ("timestamp", device_point_id),
    CONSTRAINT uq_device_points_readings_point_time UNIQUE (device_point_id, "timestamp")
);

CREATE INDEX idx_device_points_readings_point_time
    ON device_points_readings (device_point_id, "timestamp" DESC);
CREATE INDEX idx_device_points_readings_site_device_time
    ON device_points_readings (site_id, device_id, "timestamp" DESC);

COMMENT ON TABLE device_points_readings IS 'Time-series readings for device points. Stores raw and derived values.';
COMMENT ON COLUMN device_points_readings."timestamp" IS 'Timestamp when the reading was taken (UTC)';
COMMENT ON COLUMN device_points_readings.site_id IS 'Site ID (denormalized from device_points)';
COMMENT ON COLUMN device_points_readings.device_id IS 'Device ID (denormalized from device_points)';
COMMENT ON COLUMN device_points_readings.device_point_id IS 'Foreign key to device_points table';
COMMENT ON COLUMN device_points_readings.raw_value IS 'The raw value read from the device';
COMMENT ON COLUMN device_points_readings.derived_value IS 'The derived/calculated value (for bitfields, enums, scaled values)';
