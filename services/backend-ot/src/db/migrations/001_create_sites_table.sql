-- Migration: 001_create_sites_table
-- Baseline (squashed 2026-09-22 from migrations 001-049): sites where devices are deployed.

CREATE SEQUENCE sites_id_seq START WITH 1001;

CREATE TABLE sites (
    client_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    location JSONB NOT NULL,
    operator VARCHAR(255) NOT NULL,
    capacity VARCHAR(255) NOT NULL,
    device_count INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    coordinates JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_update TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id INTEGER NOT NULL DEFAULT nextval('sites_id_seq') CONSTRAINT sites_pkey PRIMARY KEY,
    deleted_at TIMESTAMPTZ,
    CONSTRAINT sites_name_key UNIQUE (name)
);

ALTER SEQUENCE sites_id_seq OWNED BY sites.id;

CREATE INDEX idx_sites_created_at ON sites (created_at);
CREATE INDEX idx_sites_name ON sites (name);
CREATE INDEX idx_sites_owner ON sites (client_id);

COMMENT ON TABLE sites IS 'Stores site/location information where devices are deployed';
COMMENT ON COLUMN sites.client_id IS 'Client identifier';
COMMENT ON COLUMN sites.name IS 'Site name';
COMMENT ON COLUMN sites.location IS 'Site location as JSON: {street: str, city: str, state: str, zip_code: int}';
COMMENT ON COLUMN sites.operator IS 'Site operator';
COMMENT ON COLUMN sites.capacity IS 'Site capacity';
COMMENT ON COLUMN sites.device_count IS 'Number of devices at this site (denormalized for performance)';
COMMENT ON COLUMN sites.description IS 'Optional site description';
COMMENT ON COLUMN sites.coordinates IS 'Geographic coordinates as JSON: {lat: float, lng: float}';
COMMENT ON COLUMN sites.created_at IS 'Timestamp when site record was created';
COMMENT ON COLUMN sites.updated_at IS 'Timestamp when site record was last updated';
COMMENT ON COLUMN sites.last_update IS 'Timestamp of last update (synced from external source)';
COMMENT ON COLUMN sites.id IS 'Primary key, 4-digit site ID';
COMMENT ON CONSTRAINT sites_name_key ON sites IS 'Ensures site names are unique';
