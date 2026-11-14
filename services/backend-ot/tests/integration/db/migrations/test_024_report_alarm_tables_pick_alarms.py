"""
Integration test for migration 024: report alarm tables stored with the old device filter
(device_ids) are converted so they still parse, keeping every other block and field as it was.
"""

from pathlib import Path

import asyncpg

from integration.factories import create_site
from schemas.reports import AlarmEventsTableBlock, ReportDefinition, RollingWindow, TextBlock
from schemas.reports.api import (
    ReportRunCreateRequest,
    ReportRunResponse,
    ReportTemplateCreateRequest,
    ReportTemplateResponse,
)

MIGRATION = Path(__file__).parents[4] / "src" / "db" / "migrations" / "024_report_alarm_tables_pick_alarms.sql"

# The blocks as they were stored before 024: an alarm table filtered by devices.
LEGACY_BLOCKS = (
    '[{"id": "intro", "kind": "text", "body": "hi", "title": null},'
    ' {"id": "alarms", "kind": "alarm_events_table", "title": "Alarms", "severity": "HIGH", "device_ids": [10, 11], "limit": 50}]'
)


class TestMigration024:
    async def test_alarm_tables_lose_their_device_filter(self, client, db: asyncpg.Connection):
        site = await create_site(client)
        report = ReportDefinition(
            window=RollingWindow(kind="rolling", duration="1H"),
            blocks=[
                TextBlock(kind="text", id="intro", body="hi"),
                AlarmEventsTableBlock(kind="alarm_events_table", id="alarms", title="Alarms", severity="HIGH", limit=50),
            ],
        )
        body = ReportTemplateCreateRequest(name="Alarms", definition=report)
        response = await client.post(f"/api/reports/site/{site.site_id}/templates", json=body.model_dump(mode="json"))
        assert response.status_code == 201, response.text
        template = ReportTemplateResponse.model_validate(response.json())
        response = await client.post(
            f"/api/reports/site/{site.site_id}/runs",
            json=ReportRunCreateRequest(template_id=template.id).model_dump(mode="json", exclude_none=True),
        )
        assert response.status_code == 202, response.text
        run = ReportRunResponse.model_validate(response.json())
        await db.execute("UPDATE report_templates SET definition = jsonb_set(definition, '{blocks}', $1::jsonb)", LEGACY_BLOCKS)
        await db.execute("UPDATE report_runs SET definition = jsonb_set(definition, '{blocks}', $1::jsonb)", LEGACY_BLOCKS)

        await db.execute(MIGRATION.read_text(encoding="utf-8"))

        response = await client.get(f"/api/reports/site/{site.site_id}/templates/{template.id}")
        assert response.status_code == 200, response.text
        converted = ReportTemplateResponse.model_validate(response.json()).definition
        assert converted == report
        response = await client.get(f"/api/reports/site/{site.site_id}/runs/{run.id}")
        assert response.status_code == 200, response.text
        assert ReportRunResponse.model_validate(response.json()).definition.blocks == report.blocks
