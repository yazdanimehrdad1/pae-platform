-- Migration: 019_add_device_points_record_enabled
-- Lets a NATIVE point be polled without storing its readings, to cut data that nobody trends.

ALTER TABLE device_points ADD COLUMN record_enabled BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE device_points ADD CONSTRAINT chk_device_points_record_enabled_category
    CHECK (record_enabled OR category = 'NATIVE');

COMMENT ON COLUMN device_points.record_enabled IS 'NATIVE points only can be FALSE: the poller stores no readings for the point (history already stored is kept). STANDARDIZED and VIRTUAL points are computed on read and always TRUE';
