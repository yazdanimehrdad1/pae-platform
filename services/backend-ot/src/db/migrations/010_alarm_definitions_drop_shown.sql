-- An alarm is shown in Active alarms exactly when it is enabled, so 'shown' goes. The limit moves
-- to enabled alarms (at most MAX_ENABLED_ALARMS per site), enforced by backend-ot under a site lock.
ALTER TABLE alarm_definitions DROP CONSTRAINT IF EXISTS chk_alarm_definitions_deleted_not_shown;
ALTER TABLE alarm_definitions DROP COLUMN IF EXISTS shown;

COMMENT ON COLUMN alarm_definitions.enabled IS 'Evaluated and shown in Active alarms (at most 20 per site); a disabled alarm raises nothing';
