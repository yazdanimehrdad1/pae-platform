-- Migration: 021_add_device_points_profile_point_description
-- A profile-owned VIRTUAL point has no formula to show, so it carries what its code computes.

ALTER TABLE device_points ADD COLUMN profile_point_description TEXT;

ALTER TABLE device_points ADD CONSTRAINT chk_device_points_profile_point_description
    CHECK (profile_point_description IS NULL OR profile_point_key IS NOT NULL);

COMMENT ON COLUMN device_points.profile_point_description IS 'VIRTUAL points owned by the site profile only: what the profile code computes, from the declared SiteVirtualPoint description (written by the profile point sync)';
