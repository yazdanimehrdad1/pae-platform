-- Migration: 022_drop_device_points_readings_point_time_index
-- Duplicates uq_device_points_readings_point_time (device_point_id, "timestamp"), which Postgres
-- scans backward for newest-first reads and every plan uses: 1.5 GB on dev, written on every insert.

DROP INDEX IF EXISTS idx_device_points_readings_point_time;
