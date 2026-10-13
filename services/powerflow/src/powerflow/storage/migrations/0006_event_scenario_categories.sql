-- Event scenario categories: 'default' scenarios are the built-in library (seeded by the app for
-- the default sites when missing) and can't be deleted; every scenario saved through the API is
-- 'custom'.
ALTER TABLE event_scenarios ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'custom'
    CHECK (category IN ('default', 'custom'));
