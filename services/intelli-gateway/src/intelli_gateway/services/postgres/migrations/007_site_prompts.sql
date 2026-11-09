-- Site scripts are now called site prompts (API contract 0.3.0): in every stored knowledge
-- (drafts and published versions) the list `site_scripts` becomes `site_prompts`, each item's
-- `script_id` becomes `prompt_id`, and the item keys in change_ids go from `script:<id>` to
-- `prompt:<id>`. Content without site scripts is left as it is.
-- (No `?` operator or LIKE pattern: the migration runner sends the SQL to the driver as is.)

UPDATE site_knowledge_drafts
SET content = (content - 'site_scripts') || jsonb_build_object(
    'site_prompts',
    COALESCE(
        (
            SELECT jsonb_agg(
                (item - 'script_id') || jsonb_build_object('prompt_id', item -> 'script_id')
                ORDER BY position
            )
            FROM jsonb_array_elements(content -> 'site_scripts')
                WITH ORDINALITY AS items(item, position)
        ),
        '[]'::jsonb
    )
)
WHERE content -> 'site_scripts' IS NOT NULL;

UPDATE site_knowledge_versions
SET content = (content - 'site_scripts') || jsonb_build_object(
    'site_prompts',
    COALESCE(
        (
            SELECT jsonb_agg(
                (item - 'script_id') || jsonb_build_object('prompt_id', item -> 'script_id')
                ORDER BY position
            )
            FROM jsonb_array_elements(content -> 'site_scripts')
                WITH ORDINALITY AS items(item, position)
        ),
        '[]'::jsonb
    )
)
WHERE content -> 'site_scripts' IS NOT NULL;

UPDATE site_knowledge_versions
SET change_ids = (
    SELECT COALESCE(
        jsonb_agg(
            CASE
                WHEN left(change_id, 7) = 'script:' THEN to_jsonb('prompt:' || substr(change_id, 8))
                ELSE to_jsonb(change_id)
            END
            ORDER BY position
        ),
        '[]'::jsonb
    )
    FROM jsonb_array_elements_text(change_ids) WITH ORDINALITY AS ids(change_id, position)
)
WHERE EXISTS (
    SELECT 1 FROM jsonb_array_elements_text(change_ids) AS ids(change_id)
    WHERE left(change_id, 7) = 'script:'
);
