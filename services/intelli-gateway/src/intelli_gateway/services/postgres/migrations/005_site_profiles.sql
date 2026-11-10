-- Site profiles: the gateway's approved copy of each site's facts (site, devices, points,
-- topology) from backend-ot, and the latest catalog fetched from backend-ot. The AI uses only the
-- latest approved version; differences wait until a site admin approves them.
-- Never network or polling details: the catalog JSON has no host, port or Modbus address.

CREATE TABLE site_profile_versions (
    site_id     BIGINT      NOT NULL,
    version     INTEGER     NOT NULL CHECK (version >= 1),
    catalog     JSONB       NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL,
    approved_by TEXT        NOT NULL,
    change_ids  JSONB       NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (site_id, version)
);

CREATE TABLE site_catalog_snapshots (
    site_id    BIGINT      PRIMARY KEY,
    catalog    JSONB       NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL
);
