-- Migration: 005_add_sites_profile
-- Links a site to the site-specific code (src/site_profiles/<profile>/) that serves its historian functions.

ALTER TABLE sites ADD COLUMN profile VARCHAR(64);

COMMENT ON COLUMN sites.profile IS 'Site profile key (a package under src/site_profiles/, e.g. alpha_solar); NULL means no site functions';
