-- Migration: 004_user_data
-- What each PlusDAS user keeps across browsers and devices: small preferences (last site, time
-- zone mode, Live Data config, ...), saved Historian trends and notes. A trend is only its
-- definition (name, point selection ids, axis scale, line styles): the readings still come from
-- backend-ot. Every row belongs to one user and goes when the user is deleted.

CREATE TABLE user_preferences (
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, key)
);

CREATE TABLE user_saved_trends (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    -- The order the user arranged them in (0 first).
    position INTEGER NOT NULL,
    name TEXT NOT NULL,
    -- Historian selection ids (points, bitfield bits, site functions, the PV forecast).
    points JSONB NOT NULL,
    scale TEXT CHECK (scale IN ('per-unit', 'per-point', 'shared')),
    -- Per selection id: what the user changed in its colour, dash and width.
    styles JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX user_saved_trends_user_idx ON user_saved_trends (user_id, position);

CREATE TABLE user_notes (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX user_notes_user_idx ON user_notes (user_id, updated_at DESC);
