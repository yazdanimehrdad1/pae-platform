-- Engineer knowledge per site (point guides, documents, device facts): one draft per site (the
-- unpublished edits, the whole knowledge as JSONB) and every published version. The AI reads
-- only the latest published version. A publish covers the whole site.

CREATE TABLE site_knowledge_drafts (
    site_id    BIGINT      PRIMARY KEY,
    revision   INTEGER     NOT NULL CHECK (revision >= 1),
    content    JSONB       NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    updated_by TEXT        NOT NULL
);

CREATE TABLE site_knowledge_versions (
    site_id       BIGINT      NOT NULL,
    version       INTEGER     NOT NULL CHECK (version >= 1),
    content       JSONB       NOT NULL,
    published_at  TIMESTAMPTZ NOT NULL,
    published_by  TEXT        NOT NULL,
    change_ids    JSONB       NOT NULL DEFAULT '[]'::jsonb,
    restored_from INTEGER,
    PRIMARY KEY (site_id, version)
);
