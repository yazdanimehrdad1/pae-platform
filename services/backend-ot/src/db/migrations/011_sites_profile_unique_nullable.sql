-- Migration: 011_sites_profile_unique_nullable
-- A profile is one site's own code: at most one site per profile. The shared 'default' profile is gone; NULL means no site-specific code yet.

ALTER TABLE sites ALTER COLUMN profile DROP DEFAULT;
ALTER TABLE sites ALTER COLUMN profile DROP NOT NULL;

-- After DROP NOT NULL: the sites that were on the shared 'default' profile now have none.
UPDATE sites SET profile = NULL WHERE profile = 'default';

-- Covers soft-deleted sites too, so restoring a site can never collide. NULLs never clash.
ALTER TABLE sites ADD CONSTRAINT sites_profile_key UNIQUE (profile);

COMMENT ON COLUMN sites.profile IS 'Site profile key (a package under src/site_profiles/individual_sites/, e.g. alpha_solar), unique per site; NULL means no site-specific code';
COMMENT ON CONSTRAINT sites_profile_key ON sites IS 'A site profile belongs to at most one site';
