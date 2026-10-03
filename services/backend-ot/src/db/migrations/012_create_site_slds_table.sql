-- Migration: 012_create_site_slds_table
-- Each site's single line diagram, one JSONB document per site, edited through /api/sites/{site_id}/sld.

CREATE TABLE site_slds (
    site_id INTEGER NOT NULL
        CONSTRAINT site_slds_pkey PRIMARY KEY
        CONSTRAINT fk_site_slds_site REFERENCES sites (id) ON DELETE CASCADE,
    document JSONB NOT NULL
        CONSTRAINT ck_site_slds_document_object CHECK (jsonb_typeof(document) = 'object'),
    revision INTEGER NOT NULL DEFAULT 1
        CONSTRAINT ck_site_slds_revision_positive CHECK (revision >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE site_slds IS 'Single line diagram per site (at most one), as a SiteSld JSON document validated by the API';
COMMENT ON COLUMN site_slds.site_id IS 'The site this diagram belongs to; deleting the site deletes it';
COMMENT ON COLUMN site_slds.document IS 'SiteSld JSON: {schema_version, nodes, buses, connections} (schemas/api_models/single_line_diagram.py)';
COMMENT ON COLUMN site_slds.revision IS 'Incremented on every save; a save must name the revision it replaces (optimistic locking)';
COMMENT ON COLUMN site_slds.created_at IS 'When the diagram was first saved';
COMMENT ON COLUMN site_slds.updated_at IS 'When the diagram was last saved';
