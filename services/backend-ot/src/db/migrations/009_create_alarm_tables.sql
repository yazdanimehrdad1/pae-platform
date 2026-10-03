-- Migration: 009_create_alarm_tables
-- System alarms per site: their definitions (built in the UI, or declared by the site's profile in
-- code), the raise/clear events the evaluation job records, and its per-definition state.

CREATE TABLE alarm_definitions (
    id SERIAL CONSTRAINT alarm_definitions_pkey PRIMARY KEY,
    site_id INTEGER NOT NULL
        CONSTRAINT fk_alarm_definitions_site_id REFERENCES sites (id) ON DELETE CASCADE,
    source VARCHAR(16) NOT NULL,
    profile_alarm_key VARCHAR(100),
    name VARCHAR(150) NOT NULL,
    kind VARCHAR(16) NOT NULL,
    rule JSONB,
    severity VARCHAR(16) NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    notify_mobile BOOLEAN NOT NULL DEFAULT FALSE,
    notify_email BOOLEAN NOT NULL DEFAULT FALSE,
    shown BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT chk_alarm_definitions_source CHECK (source IN ('USER', 'PROFILE')),
    CONSTRAINT chk_alarm_definitions_kind CHECK (kind IN ('threshold', 'comms_stale', 'condition', 'profile')),
    CONSTRAINT chk_alarm_definitions_severity CHECK (severity IN ('fault', 'warning')),
    -- A user alarm carries its rule; a profile alarm's logic is code, found by its key.
    CONSTRAINT chk_alarm_definitions_user_rule CHECK (
        (source = 'USER' AND rule IS NOT NULL AND profile_alarm_key IS NULL AND kind <> 'profile')
        OR (source = 'PROFILE' AND rule IS NULL AND profile_alarm_key IS NOT NULL AND kind = 'profile')
    ),
    CONSTRAINT chk_alarm_definitions_deleted_not_shown CHECK (deleted_at IS NULL OR NOT shown)
);

-- Names are identifiers: unique per site ignoring case, among alarms that aren't deleted.
CREATE UNIQUE INDEX uq_alarm_definitions_site_name ON alarm_definitions (site_id, lower(name))
    WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_alarm_definitions_site_profile_key ON alarm_definitions (site_id, profile_alarm_key)
    WHERE profile_alarm_key IS NOT NULL;
CREATE INDEX idx_alarm_definitions_site_id ON alarm_definitions (site_id);

COMMENT ON TABLE alarm_definitions IS 'Alarms of a site: USER (built in the UI) or PROFILE (declared by the site profile in code)';
COMMENT ON COLUMN alarm_definitions.source IS 'USER: built in the UI; PROFILE: declared in site_profiles code';
COMMENT ON COLUMN alarm_definitions.profile_alarm_key IS 'PROFILE only: the SiteAlarm key in the site profile';
COMMENT ON COLUMN alarm_definitions.name IS 'Identifier: letters, digits, underscore, not starting with a digit; unique per site ignoring case';
COMMENT ON COLUMN alarm_definitions.kind IS 'threshold, comms_stale or condition (USER), or profile';
COMMENT ON COLUMN alarm_definitions.rule IS 'USER only: what the alarm checks (JSON, see AlarmRule)';
COMMENT ON COLUMN alarm_definitions.shown IS 'Shown in the Active alarms section (at most 10 per site); every enabled alarm is evaluated regardless';
COMMENT ON COLUMN alarm_definitions.deleted_at IS 'Set when deleted: no longer evaluated or shown; its events stay in history';

CREATE TABLE alarm_events (
    id BIGSERIAL CONSTRAINT alarm_events_pkey PRIMARY KEY,
    definition_id INTEGER NOT NULL
        CONSTRAINT fk_alarm_events_definition_id REFERENCES alarm_definitions (id) ON DELETE CASCADE,
    site_id INTEGER NOT NULL
        CONSTRAINT fk_alarm_events_site_id REFERENCES sites (id) ON DELETE CASCADE,
    device_id INTEGER
        CONSTRAINT fk_alarm_events_device_id REFERENCES devices (device_id) ON DELETE SET NULL,
    severity VARCHAR(16) NOT NULL,
    raised_at TIMESTAMPTZ NOT NULL,
    cleared_at TIMESTAMPTZ,
    value_at_raise DOUBLE PRECISION,
    message TEXT NOT NULL DEFAULT '',
    CONSTRAINT chk_alarm_events_severity CHECK (severity IN ('fault', 'warning')),
    CONSTRAINT chk_alarm_events_cleared_after_raised CHECK (cleared_at IS NULL OR cleared_at >= raised_at)
);

-- At most one active (uncleared) event per alarm.
CREATE UNIQUE INDEX uq_alarm_events_one_active ON alarm_events (definition_id) WHERE cleared_at IS NULL;
CREATE INDEX idx_alarm_events_site_raised ON alarm_events (site_id, raised_at);

COMMENT ON TABLE alarm_events IS 'One raise of an alarm, and its clear (cleared_at NULL while active)';
COMMENT ON COLUMN alarm_events.device_id IS 'The device the alarm is about, or NULL for a site-level alarm';
COMMENT ON COLUMN alarm_events.value_at_raise IS 'The watched value when it raised, when there is one';

CREATE TABLE alarm_evaluation_state (
    definition_id INTEGER CONSTRAINT alarm_evaluation_state_pkey PRIMARY KEY
        CONSTRAINT fk_alarm_evaluation_state_definition_id REFERENCES alarm_definitions (id) ON DELETE CASCADE,
    condition_since TIMESTAMPTZ,
    last_evaluated_at TIMESTAMPTZ
);

COMMENT ON TABLE alarm_evaluation_state IS 'The evaluation job''s memory between runs, per alarm';
COMMENT ON COLUMN alarm_evaluation_state.condition_since IS 'When the alarm condition started holding (for the raise delay); NULL when it does not hold';
