-- Migration: 016_alarm_evaluation_state_clear_since
-- The clear delay timer: an active alarm clears only after its clear test has passed for clear_delay_sec.

ALTER TABLE alarm_evaluation_state ADD COLUMN clear_since TIMESTAMPTZ;

COMMENT ON COLUMN alarm_evaluation_state.clear_since IS 'When an active alarm''s clear test started passing (for the clear delay); NULL when it does not pass';
