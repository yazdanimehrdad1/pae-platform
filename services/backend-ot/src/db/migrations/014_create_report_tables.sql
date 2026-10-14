-- Migration: 014_create_report_tables
-- Reports: templates (what a report contains) and runs (a queued or generated report, with its
-- stored result), edited and read through /api/reports. Schedules come in a later migration.

CREATE TABLE report_templates (
    id SERIAL CONSTRAINT report_templates_pkey PRIMARY KEY,
    site_id INTEGER NOT NULL
        CONSTRAINT fk_report_templates_site_id REFERENCES sites (id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    definition JSONB NOT NULL
        CONSTRAINT ck_report_templates_definition_object CHECK (jsonb_typeof(definition) = 'object'),
    version INTEGER NOT NULL DEFAULT 1
        CONSTRAINT ck_report_templates_version_positive CHECK (version >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_report_templates_site_name ON report_templates (site_id, lower(name));

COMMENT ON TABLE report_templates IS 'Report templates of a site: a ReportDefinition (window + blocks) with a name';
COMMENT ON COLUMN report_templates.name IS 'Unique per site, ignoring case';
COMMENT ON COLUMN report_templates.definition IS 'ReportDefinition JSON (schemas/reports/definition.py)';
COMMENT ON COLUMN report_templates.version IS 'Starts at 1; incremented each time the definition changes';

CREATE TABLE report_runs (
    id BIGSERIAL CONSTRAINT report_runs_pkey PRIMARY KEY,
    site_id INTEGER NOT NULL
        CONSTRAINT fk_report_runs_site_id REFERENCES sites (id) ON DELETE CASCADE,
    template_id INTEGER
        CONSTRAINT fk_report_runs_template_id REFERENCES report_templates (id) ON DELETE SET NULL,
    template_version INTEGER,
    name VARCHAR(150) NOT NULL,
    definition JSONB NOT NULL
        CONSTRAINT ck_report_runs_definition_object CHECK (jsonb_typeof(definition) = 'object'),
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'queued',
    trigger VARCHAR(16) NOT NULL DEFAULT 'manual',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error TEXT,
    result JSONB,
    CONSTRAINT chk_report_runs_status CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    CONSTRAINT chk_report_runs_trigger CHECK (trigger IN ('manual', 'schedule')),
    CONSTRAINT chk_report_runs_window CHECK (window_start < window_end),
    CONSTRAINT chk_report_runs_result_when_succeeded CHECK ((status = 'succeeded') = (result IS NOT NULL))
);

CREATE INDEX idx_report_runs_site_requested ON report_runs (site_id, requested_at DESC);
CREATE INDEX idx_report_runs_queued ON report_runs (requested_at) WHERE status = 'queued';

COMMENT ON TABLE report_runs IS 'One report: queued, being generated, generated (result stored) or failed';
COMMENT ON COLUMN report_runs.template_id IS 'The template it was generated from; NULL for an ad-hoc report or once the template is deleted';
COMMENT ON COLUMN report_runs.definition IS 'The ReportDefinition it was generated from, copied at request time';
COMMENT ON COLUMN report_runs.window_start IS 'The resolved report window (UTC), fixed when the run was requested';
COMMENT ON COLUMN report_runs.result IS 'ReportSnapshot JSON (schemas/reports/snapshot.py); set only when status is succeeded';
