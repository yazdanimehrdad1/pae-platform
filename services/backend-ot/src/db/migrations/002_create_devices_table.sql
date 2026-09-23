-- Migration: 002_create_devices_table
-- Baseline (squashed 2026-09-22 from migrations 001-049): Modbus devices, scoped to a site.

CREATE SEQUENCE devices_id_seq AS INTEGER;

CREATE TABLE devices (
    device_id INTEGER NOT NULL DEFAULT nextval('devices_id_seq') CONSTRAINT devices_pkey PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL DEFAULT 502,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    poll_enabled BOOLEAN DEFAULT TRUE,
    site_id INTEGER NOT NULL
        CONSTRAINT fk_devices_site_id REFERENCES sites (id) ON DELETE CASCADE,
    timeout DOUBLE PRECISION,
    server_address INTEGER NOT NULL DEFAULT 1,
    read_from_aggregator BOOLEAN NOT NULL DEFAULT TRUE,
    type VARCHAR(50) NOT NULL,
    vendor VARCHAR(255),
    model VARCHAR(255),
    protocol VARCHAR(20) NOT NULL DEFAULT 'Modbus',
    scan_ranges JSONB,
    scan_ranges_locked BOOLEAN NOT NULL DEFAULT FALSE,
    modbus_address_mode VARCHAR(20) NOT NULL DEFAULT 'zero_based',
    deleted_at TIMESTAMPTZ,
    CONSTRAINT devices_type_check CHECK (
        type IN ('BESS', 'ES', 'INVERTER', 'PV', 'GENERATOR', 'LOADBANK', 'RELAY', 'IED', 'METER', 'RTAC')
    )
);

ALTER SEQUENCE devices_id_seq OWNED BY devices.device_id;

CREATE INDEX idx_devices_host_port ON devices (host, port);
CREATE INDEX idx_devices_name ON devices (name);
CREATE INDEX idx_devices_site_id ON devices (site_id);
CREATE UNIQUE INDEX uq_devices_name_site_id ON devices (name, site_id) WHERE site_id IS NOT NULL;

COMMENT ON TABLE devices IS 'Stores Modbus device configuration and connection information';
COMMENT ON COLUMN devices.device_id IS 'Primary key, auto-incrementing';
COMMENT ON COLUMN devices.name IS 'Device name/identifier (globally unique)';
COMMENT ON COLUMN devices.host IS 'Device hostname or IP address';
COMMENT ON COLUMN devices.port IS 'Device port (default: 502)';
COMMENT ON COLUMN devices.description IS 'Optional device description';
COMMENT ON COLUMN devices.created_at IS 'Timestamp when device record was created';
COMMENT ON COLUMN devices.updated_at IS 'Timestamp when device record was last updated';
COMMENT ON COLUMN devices.poll_enabled IS 'Whether polling is enabled for this device';
COMMENT ON COLUMN devices.site_id IS 'Site ID (required)';
COMMENT ON COLUMN devices.timeout IS 'Optional timeout (seconds)';
COMMENT ON COLUMN devices.server_address IS 'Server address';
COMMENT ON COLUMN devices.read_from_aggregator IS 'Whether to read from edge aggregator';
COMMENT ON COLUMN devices.type IS 'Device type';
COMMENT ON COLUMN devices.vendor IS 'Device vendor';
COMMENT ON COLUMN devices.model IS 'Device model';
