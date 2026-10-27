-- Migration: 020_add_device_points_profile_point
-- A site profile can own a VIRTUAL point whose values a scheduled job computes and stores.

ALTER TABLE device_points ADD COLUMN profile_point_key VARCHAR(100);

ALTER TABLE device_points ADD CONSTRAINT chk_device_points_profile_point_category
    CHECK (profile_point_key IS NULL OR (category = 'VIRTUAL' AND virtual_definition IS NULL));

ALTER TABLE device_points ADD CONSTRAINT uq_device_points_device_profile_point_key
    UNIQUE (device_id, profile_point_key);

COMMENT ON COLUMN device_points.profile_point_key IS 'VIRTUAL points owned by the site profile only: the declared SiteVirtualPoint key. Its values are computed by the job profile_point_compute and stored in device_points_readings, not computed on read';

COMMENT ON COLUMN device_points.virtual_definition IS 'VIRTUAL points only: the condition or calculation (JSON, see VirtualPointDefinition) computed on read from other points on the site';

COMMENT ON COLUMN device_points.record_enabled IS 'NATIVE points only can be FALSE: the poller stores no readings for the point (history already stored is kept). STANDARDIZED and VIRTUAL points are always TRUE';

CREATE TABLE profile_point_state (
    device_point_id INTEGER PRIMARY KEY
        CONSTRAINT fk_profile_point_state_device_point_id REFERENCES device_points (id) ON DELETE CASCADE,
    computed_until TIMESTAMPTZ NOT NULL
);

COMMENT ON TABLE profile_point_state IS 'Per profile-owned VIRTUAL point: how far the job profile_point_compute has computed and stored its values';
COMMENT ON COLUMN profile_point_state.computed_until IS 'End (inclusive) of the last window computed; the next run starts after it';
