-- Migration: 023_alarm_severity_high_medium_low
-- Alarm severity moves from fault/warning to the points' scale: HIGH, MEDIUM, LOW.
-- Existing rows: fault -> HIGH, warning -> MEDIUM (no alarm loses urgency). Profile alarms get
-- their declared severity on the next profile sync. Stored report definitions and results
-- (alarm events table blocks) are converted the same way, so they still parse.

ALTER TABLE alarm_definitions DROP CONSTRAINT chk_alarm_definitions_severity;
ALTER TABLE alarm_events DROP CONSTRAINT chk_alarm_events_severity;

UPDATE alarm_definitions SET severity = CASE severity WHEN 'fault' THEN 'HIGH' ELSE 'MEDIUM' END
    WHERE severity IN ('fault', 'warning');
UPDATE alarm_events SET severity = CASE severity WHEN 'fault' THEN 'HIGH' ELSE 'MEDIUM' END
    WHERE severity IN ('fault', 'warning');

ALTER TABLE alarm_definitions ADD CONSTRAINT chk_alarm_definitions_severity
    CHECK (severity IN ('HIGH', 'MEDIUM', 'LOW'));
ALTER TABLE alarm_events ADD CONSTRAINT chk_alarm_events_severity
    CHECK (severity IN ('HIGH', 'MEDIUM', 'LOW'));

COMMENT ON COLUMN alarm_definitions.severity IS 'HIGH, MEDIUM or LOW (the same scale as device_points.severity)';
COMMENT ON COLUMN alarm_events.severity IS 'The alarm''s severity when it raised: HIGH, MEDIUM or LOW';

-- Report JSON: only alarm events table blocks (the filter) and their rows carry an alarm severity.
UPDATE report_templates SET definition = replace(replace(definition::text,
    '"severity": "fault"', '"severity": "HIGH"'), '"severity": "warning"', '"severity": "MEDIUM"')::jsonb
    WHERE definition::text LIKE '%"severity": "fault"%' OR definition::text LIKE '%"severity": "warning"%';
UPDATE report_runs SET definition = replace(replace(definition::text,
    '"severity": "fault"', '"severity": "HIGH"'), '"severity": "warning"', '"severity": "MEDIUM"')::jsonb
    WHERE definition::text LIKE '%"severity": "fault"%' OR definition::text LIKE '%"severity": "warning"%';
UPDATE report_runs SET result = replace(replace(result::text,
    '"severity": "fault"', '"severity": "HIGH"'), '"severity": "warning"', '"severity": "MEDIUM"')::jsonb
    WHERE result::text LIKE '%"severity": "fault"%' OR result::text LIKE '%"severity": "warning"%';
