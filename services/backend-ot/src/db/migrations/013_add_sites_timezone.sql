-- Migration: 013_add_sites_timezone
-- A site's local time zone, so "daily"/"monthly" report windows and schedules have a defined day.

ALTER TABLE sites ADD COLUMN timezone VARCHAR(64) NOT NULL DEFAULT 'UTC';

COMMENT ON COLUMN sites.timezone IS 'IANA time zone of the site (e.g. America/Los_Angeles), stored canonical; local days and report schedules resolve in it';
