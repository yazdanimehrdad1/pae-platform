-- Migration: 007_add_device_points_class_and_severity
-- Optional point classification: what kind of signal a point carries ("class") and how serious it is ("severity").

ALTER TABLE device_points ADD COLUMN "class" VARCHAR(16);
ALTER TABLE device_points ADD COLUMN severity VARCHAR(16);

ALTER TABLE device_points ADD CONSTRAINT chk_device_points_class
    CHECK ("class" IN ('ANALOG', 'BINARY', 'ALARM', 'CONTROL'));
ALTER TABLE device_points ADD CONSTRAINT chk_device_points_severity
    CHECK (severity IN ('HIGH', 'MEDIUM', 'LOW'));

COMMENT ON COLUMN device_points."class" IS 'Optional signal class: ANALOG (metered/continuous), BINARY (state/status/flags), ALARM (warning/fault/error/trip), CONTROL (setpoint/command/config)';
COMMENT ON COLUMN device_points.severity IS 'Optional severity: HIGH, MEDIUM or LOW';
