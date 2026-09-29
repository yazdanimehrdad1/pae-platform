-- Migration: 008_add_device_points_virtual_definition
-- How a VIRTUAL point's value is computed from other points each poll cycle (condition or calculation).

ALTER TABLE device_points ADD COLUMN virtual_definition JSONB;

ALTER TABLE device_points ADD CONSTRAINT chk_device_points_virtual_definition_category
    CHECK (virtual_definition IS NULL OR category = 'VIRTUAL');

COMMENT ON COLUMN device_points.virtual_definition IS 'VIRTUAL points only: the condition or calculation (JSON, see VirtualPointDefinition) evaluated each poll cycle from other points on the site';
