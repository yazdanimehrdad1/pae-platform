-- Migration: 018_add_device_points_source_point_id
-- A STANDARDIZED point shows the readings of a real point on its device, once linked through the API.

ALTER TABLE device_points ADD COLUMN source_point_id INTEGER
    CONSTRAINT fk_device_points_source_point_id REFERENCES device_points (id) ON DELETE SET NULL;

ALTER TABLE device_points ADD CONSTRAINT chk_device_points_source_point_category
    CHECK (source_point_id IS NULL OR category = 'STANDARDIZED');

COMMENT ON COLUMN device_points.source_point_id IS 'STANDARDIZED points only: the NATIVE point on the same device whose readings it shows (times scale_factor, in unit); set with PUT /api/device-points/.../{point_id}/link';
