-- powerflow configuration store: sites, their Modbus maps, and the active site.
-- Profiles are CSV files for now (ProfileStore), not tables.

CREATE TABLE IF NOT EXISTS sites (
    name        TEXT PRIMARY KEY,
    config      JSONB NOT NULL,          -- a SiteConfig, validated by the app before writing
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS modbus_maps (
    site        TEXT NOT NULL REFERENCES sites (name) ON DELETE CASCADE,
    asset       TEXT NOT NULL,           -- <asset_type>.<asset_id>, e.g. pv.pv1
    map         JSONB NOT NULL,          -- a ModbusMap, validated by the app before writing
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (site, asset)
);

-- Single-row settings; key 'active_site' holds {"site": "<name>"}.
CREATE TABLE IF NOT EXISTS app_state (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
