-- Migration: 024_report_alarm_tables_pick_alarms
-- A report's alarm events table now picks the site's alarms (alarm_ids) instead of devices
-- (device_ids): a device filter hid every site-wide event (device_id NULL). Stored report
-- definitions drop device_ids so they still parse; such a table then lists all the site's alarms
-- (alarm_ids empty) until its author picks some. Stored results keep their rows as generated.

-- One definition's blocks with device_ids removed from its alarm events tables, order kept.
CREATE FUNCTION pg_temp.drop_alarm_table_devices(definition JSONB) RETURNS JSONB
LANGUAGE SQL IMMUTABLE AS $$
    SELECT jsonb_set(definition, '{blocks}', COALESCE((
        SELECT jsonb_agg(
            CASE WHEN block->>'kind' = 'alarm_events_table' THEN block - 'device_ids' ELSE block END
            ORDER BY position
        )
        FROM jsonb_array_elements(definition->'blocks') WITH ORDINALITY AS blocks(block, position)
    ), '[]'::jsonb))
$$;

UPDATE report_templates SET definition = pg_temp.drop_alarm_table_devices(definition)
    WHERE definition->'blocks' @> '[{"kind": "alarm_events_table"}]';
UPDATE report_runs SET definition = pg_temp.drop_alarm_table_devices(definition)
    WHERE definition->'blocks' @> '[{"kind": "alarm_events_table"}]';
UPDATE report_runs SET result = jsonb_set(result, '{definition}', pg_temp.drop_alarm_table_devices(result->'definition'))
    WHERE result->'definition'->'blocks' @> '[{"kind": "alarm_events_table"}]';
