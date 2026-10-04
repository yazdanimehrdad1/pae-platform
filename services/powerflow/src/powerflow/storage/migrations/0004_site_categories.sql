-- Site categories: 'default' sites ship with powerflow (migration 0003) and can't be deleted;
-- every site created through the API is 'custom'. Only migrations set 'default'.
ALTER TABLE sites ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'custom'
    CHECK (category IN ('default', 'custom'));

-- The default sites were renamed. A database that ran 0003 under the old names gets the new ones
-- (skipped if a site already has the new name); a fresh database already has them.
UPDATE sites SET name = '2bess_1pv', updated_at = now()
    WHERE name = 'reference_2bess_1pv' AND NOT EXISTS (SELECT 1 FROM sites WHERE name = '2bess_1pv');
UPDATE sites SET name = '1bess_1pv', updated_at = now()
    WHERE name = 'small_1bess_1pv' AND NOT EXISTS (SELECT 1 FROM sites WHERE name = '1bess_1pv');
UPDATE sites SET name = '3bess_2pv', updated_at = now()
    WHERE name = 'three_bess_two_pv' AND NOT EXISTS (SELECT 1 FROM sites WHERE name = '3bess_2pv');

UPDATE app_state SET value = jsonb_build_object('site', CASE value->>'site'
        WHEN 'reference_2bess_1pv' THEN '2bess_1pv'
        WHEN 'small_1bess_1pv' THEN '1bess_1pv'
        WHEN 'three_bess_two_pv' THEN '3bess_2pv'
    END), updated_at = now()
    WHERE key = 'active_site'
      AND value->>'site' IN ('reference_2bess_1pv', 'small_1bess_1pv', 'three_bess_two_pv');

UPDATE sites SET category = 'default' WHERE name IN ('2bess_1pv', '1bess_1pv', '3bess_2pv');
