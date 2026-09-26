-- Migration: 006_sites_profile_not_null
-- Every site has a profile: sites without site-specific code use the built-in 'default' profile.

UPDATE sites SET profile = 'default' WHERE profile IS NULL;

ALTER TABLE sites ALTER COLUMN profile SET DEFAULT 'default';
ALTER TABLE sites ALTER COLUMN profile SET NOT NULL;

COMMENT ON COLUMN sites.profile IS 'Site profile key (a package under src/site_profiles/, e.g. alpha_solar); ''default'' offers only the common endpoints';
