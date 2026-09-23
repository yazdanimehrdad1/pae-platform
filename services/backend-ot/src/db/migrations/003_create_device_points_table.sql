-- Migration: 003_create_device_points_table
-- Baseline (squashed 2026-09-22 from migrations 001-049): points (registers) defined on a device.

CREATE TYPE device_point_category AS ENUM ('NATIVE', 'STANDARDIZED', 'VIRTUAL');

CREATE TABLE device_points (
    id SERIAL CONSTRAINT device_points_pkey PRIMARY KEY,
    site_id INTEGER NOT NULL
        CONSTRAINT fk_device_points_site_id REFERENCES sites (id) ON DELETE CASCADE,
    device_id INTEGER NOT NULL
        CONSTRAINT device_points_device_id_fkey REFERENCES devices (device_id) ON DELETE CASCADE,
    address INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    size INTEGER NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    scale_factor DOUBLE PRECISION,
    unit VARCHAR(50),
    enum_detail JSON,
    bitfield_detail JSON,
    byte_order VARCHAR(20) NOT NULL DEFAULT 'big-endian',
    word_order VARCHAR(20) NOT NULL DEFAULT 'msw_first',
    category device_point_category NOT NULL DEFAULT 'NATIVE',
    poll_kind VARCHAR(20),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT uq_device_point_site_device_name UNIQUE (site_id, device_id, name)
);

CREATE INDEX idx_device_points_device_id ON device_points (device_id);
