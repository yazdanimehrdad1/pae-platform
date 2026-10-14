-- Migration: 015_create_report_schedules
-- Report schedules: generate a template's report on a cadence (in the site's time zone) and keep
-- only as many of those reports as the schedule says. Each scheduled report names its schedule.

CREATE TABLE report_schedules (
    id SERIAL CONSTRAINT report_schedules_pkey PRIMARY KEY,
    site_id INTEGER NOT NULL
        CONSTRAINT fk_report_schedules_site_id REFERENCES sites (id) ON DELETE CASCADE,
    template_id INTEGER NOT NULL
        CONSTRAINT fk_report_schedules_template_id REFERENCES report_templates (id) ON DELETE CASCADE,
    cadence JSONB NOT NULL
        CONSTRAINT ck_report_schedules_cadence_object CHECK (jsonb_typeof(cadence) = 'object'),
    window_override JSONB
        CONSTRAINT ck_report_schedules_window_object CHECK (window_override IS NULL OR jsonb_typeof(window_override) = 'object'),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    keep_last INTEGER
        CONSTRAINT ck_report_schedules_keep_last CHECK (keep_last IS NULL OR keep_last >= 1),
    keep_days INTEGER
        CONSTRAINT ck_report_schedules_keep_days CHECK (keep_days IS NULL OR keep_days >= 1),
    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_report_schedules_site ON report_schedules (site_id);
CREATE INDEX idx_report_schedules_due ON report_schedules (next_run_at) WHERE enabled;

COMMENT ON TABLE report_schedules IS 'Generate a template''s report on a cadence, keeping only some of those reports';
COMMENT ON COLUMN report_schedules.template_id IS 'The template generated; deleting the template deletes its schedules (its reports stay)';
COMMENT ON COLUMN report_schedules.cadence IS 'ReportCadence JSON: hourly/daily/weekly/monthly, in the site time zone (schemas/reports/schedules.py)';
COMMENT ON COLUMN report_schedules.window_override IS 'A ReportWindow replacing the template''s for these reports; NULL keeps the template''s';
COMMENT ON COLUMN report_schedules.keep_last IS 'Keep at most this many of the schedule''s reports (newest); NULL keeps all';
COMMENT ON COLUMN report_schedules.keep_days IS 'Delete the schedule''s reports requested more than this many days ago; NULL keeps them';
COMMENT ON COLUMN report_schedules.next_run_at IS 'When it next generates; NULL while disabled';

ALTER TABLE report_runs ADD COLUMN schedule_id INTEGER
    CONSTRAINT fk_report_runs_schedule_id REFERENCES report_schedules (id) ON DELETE SET NULL;
CREATE INDEX idx_report_runs_schedule ON report_runs (schedule_id, requested_at DESC) WHERE schedule_id IS NOT NULL;
COMMENT ON COLUMN report_runs.schedule_id IS 'The schedule that generated it; NULL for a report requested by hand, or once the schedule is deleted';
