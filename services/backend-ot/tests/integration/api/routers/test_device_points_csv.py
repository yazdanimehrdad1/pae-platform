"""
Integration tests for a device's points as CSV: the template, the export, and the import.

Invariant guarded: the template is the points table's header row (the old snake_case headers still
import); the export is the device's active NATIVE
points and imports back unchanged; a dry run (the default) reports the plan and every problem and
writes nothing; an applied import creates, updates every field (a blank cell clears it), restores
a deleted point, and with delete_missing soft-deletes the points not in the file (restorable), all
in one transaction with the scan ranges recomputed; a file with problems gets 400 with every
problem and changes nothing; deleting or stopping the recording of a point something reads gets
409 and changes nothing; an unknown device is 404, a non-UTF-8 or too large body 400/413.
"""

from httpx import AsyncClient

from integration.factories import (
    create_device,
    create_linked_bess,
    create_site,
    device_points,
    point_request,
    upsert_points,
)
from schemas.api_models import PointsCsvImportResult

TABLE_HEADER = (
    "Name,Record,Poll Kind,Address,Size,Data Type,Unit,Scale,Byte Order,Word Order,Class,"
    "Severity,Enum / Bit Labels"
)
# The import rows below use the old snake_case columns (still read), the shortest to type.
HEADER = "name,poll_kind,address,data_type,scale_factor,unit,byte_order,word_order,class,severity,record,labels"


def base(site_id: int, device_id: int) -> str:
    return f"/api/device-points/site/{site_id}/device/{device_id}"


async def import_csv(
    client: AsyncClient, site_id: int, device_id: int, text: str, **params: object
):
    return await client.post(
        f"{base(site_id, device_id)}/csv-import",
        content=text.encode("utf-8"),
        headers={"Content-Type": "text/csv"},
        params={key: str(value).lower() for key, value in params.items()},
    )


async def device_with_points(client: AsyncClient) -> tuple[int, int]:
    site = await create_site(client)
    device = await create_device(client, site.site_id)
    await upsert_points(
        client,
        site.site_id,
        device.device_id,
        [
            point_request(name="W", address=100, size=2, data_type="float32", unit="kW"),
            point_request(
                name="InvSt",
                address=102,
                size=1,
                data_type="enum16",
                unit=None,
                enum_detail={"1": "OFF", "3": "RUNNING"},
                point_class="BINARY",
            ),
            point_request(name="Old", address=200, size=1, data_type="int16", unit=None),
        ],
    )
    return site.site_id, device.device_id


class TestTemplateAndExport:
    async def test_template(self, client: AsyncClient) -> None:
        response = await client.get("/api/device-points/csv-template")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "device-points-template.csv" in response.headers["content-disposition"]
        assert response.text == TABLE_HEADER + "\r\n"

    async def test_export_and_reimport_is_unchanged(self, client: AsyncClient) -> None:
        site_id, device_id = await device_with_points(client)
        response = await client.get(f"{base(site_id, device_id)}/csv")
        assert response.status_code == 200
        assert "rtac-1-points.csv" in response.headers["content-disposition"]
        lines = response.text.splitlines()
        assert lines == [
            TABLE_HEADER,
            "W,Yes,holding,100,2,float32,kW,1,big,msw_first,,,",
            "InvSt,Yes,holding,102,1,enum16,,1,big,msw_first,BINARY,,1=OFF; 3=RUNNING",
            "Old,Yes,holding,200,1,int16,,1,big,msw_first,,,",
        ]
        result = PointsCsvImportResult.model_validate(
            (await import_csv(client, site_id, device_id, response.text)).json()
        )
        assert result.unchanged == ["W", "InvSt", "Old"]
        assert not (
            result.created or result.updated or result.missing or result.errors or result.applied
        )

    async def test_unknown_device(self, client: AsyncClient) -> None:
        site = await create_site(client)
        assert (await client.get(f"{base(site.site_id, 999)}/csv")).status_code == 404
        assert (await import_csv(client, site.site_id, 999, HEADER)).status_code == 404


class TestImport:
    CHANGED = "\r\n".join(
        [
            HEADER,
            "W,holding,100,float32,,,little,,,,,",  # unit cleared, byte order changed
            "InvSt,holding,102,enum16,,,,,BINARY,,,1=OFF; 3=RUNNING; 4=FAULT",
            "New,input,0,uint16,0.1,%,,,ANALOG,LOW,no,",
        ]
    )

    async def test_a_dry_run_reports_and_writes_nothing(self, client: AsyncClient) -> None:
        site_id, device_id = await device_with_points(client)
        before = await device_points(client, site_id, device_id)
        response = await import_csv(client, site_id, device_id, self.CHANGED)
        assert response.status_code == 200, response.text
        result = PointsCsvImportResult.model_validate(response.json())
        assert result.applied is False
        assert result.created == ["New"]
        assert [(change.name, change.fields) for change in result.updated] == [
            ("W", ["Unit", "Byte Order"]),
            ("InvSt", ["Enum / Bit Labels"]),
        ]
        assert result.missing == ["Old"] and result.deleted == [] and result.errors == []
        assert await device_points(client, site_id, device_id) == before

    async def test_apply_creates_updates_clears_and_deletes_missing(
        self, client: AsyncClient
    ) -> None:
        site_id, device_id = await device_with_points(client)
        response = await import_csv(
            client, site_id, device_id, self.CHANGED, dry_run=False, delete_missing=True
        )
        assert response.status_code == 200, response.text
        result = PointsCsvImportResult.model_validate(response.json())
        assert result.applied and result.deleted == ["Old"]

        points = await device_points(client, site_id, device_id)
        assert "Old" not in points
        assert (points["W"].unit, points["W"].byte_order) == (None, "little")
        assert points["InvSt"].enum_detail == {"1": "OFF", "3": "RUNNING", "4": "FAULT"}
        new = points["New"]
        assert (new.poll_kind, new.address, new.size, new.scale_factor, new.unit) == (
            "input",
            0,
            1,
            0.1,
            "%",
        )
        assert (new.point_class, new.severity, new.record_enabled, new.category) == (
            "ANALOG",
            "LOW",
            False,
            "NATIVE",
        )

        deleted = await client.get(f"{base(site_id, device_id)}/deleted")
        assert [point["name"] for point in deleted.json()] == ["Old"]
        device = (await client.get(f"/api/devices/site/{site_id}/devices/{device_id}")).json()
        assert device["scan_ranges"]["input"] == [
            {"start_index": 0, "count": 1}
        ]  # recomputed for New

    async def test_reimporting_a_deleted_point_restores_it(self, client: AsyncClient) -> None:
        site_id, device_id = await device_with_points(client)
        rows = HEADER + "\r\nW,holding,100,float32,,kW,,,,,,\r\n"
        await import_csv(client, site_id, device_id, rows, dry_run=False, delete_missing=True)
        restored = await import_csv(
            client, site_id, device_id, rows + "Old,holding,200,int16,,,,,,,,\r\n", dry_run=False
        )
        result = PointsCsvImportResult.model_validate(restored.json())
        assert [(change.name, change.fields) for change in result.updated] == [
            ("Old", ["restored"])
        ]
        assert "Old" in await device_points(client, site_id, device_id)

    async def test_a_file_with_problems_changes_nothing(self, client: AsyncClient) -> None:
        site_id, device_id = await device_with_points(client)
        before = await device_points(client, site_id, device_id)
        bad = "\r\n".join(
            [
                HEADER,
                "X,holding,0,int8,,,,,,,,",
                "Y,holding,101,int16,,,,,,,,",
                "Z,holding,300,int16",
            ]
        )
        dry = PointsCsvImportResult.model_validate(
            (await import_csv(client, site_id, device_id, bad)).json()
        )
        assert [(error.line, error.column) for error in dry.errors] == [
            (2, "Data Type"),
            (3, "Address"),
        ]

        applied = await import_csv(client, site_id, device_id, bad, dry_run=False)
        assert applied.status_code == 400
        detail = applied.json()["detail"]
        assert detail["error"] == "ValidationError"
        assert [(error["line"], error["column"]) for error in detail["errors"]] == [
            (2, "Data Type"),
            (3, "Address"),
        ]
        assert await device_points(client, site_id, device_id) == before

    async def test_a_standardized_point_name_is_refused(self, client: AsyncClient) -> None:
        bess = await create_linked_bess(client)
        text = HEADER + "\r\nBESS_ACTIVE_POWER,holding,0,int16\r\n"
        result = PointsCsvImportResult.model_validate(
            (await import_csv(client, bess.site_id, bess.device_id, text)).json()
        )
        assert [(error.line, error.column) for error in result.errors] == [(2, "Name")]

    async def test_deleting_or_unrecording_a_point_something_reads_is_refused(
        self, client: AsyncClient
    ) -> None:
        bess = await create_linked_bess(client)
        before = await device_points(client, bess.site_id, bess.device_id)
        only_soc = HEADER + "\r\nSoC,holding,110,float32,,%,,,,,,\r\n"
        delete = await import_csv(
            client, bess.site_id, bess.device_id, only_soc, dry_run=False, delete_missing=True
        )
        assert delete.status_code == 409, delete.text
        assert "BESS_ACTIVE_POWER" in delete.json()["detail"]["message"]

        unrecord = (
            HEADER + "\r\nW,holding,100,float32,,W,,,,,no,\r\nSoC,holding,110,float32,,%,,,,,,\r\n"
        )
        stop = await import_csv(client, bess.site_id, bess.device_id, unrecord, dry_run=False)
        assert stop.status_code == 409, stop.text
        assert await device_points(client, bess.site_id, bess.device_id) == before

    async def test_body_checks(self, client: AsyncClient) -> None:
        site_id, device_id = await device_with_points(client)
        not_utf8 = await client.post(
            f"{base(site_id, device_id)}/csv-import",
            content=b"\xff\xfe\x00",
            headers={"Content-Type": "text/csv"},
        )
        assert not_utf8.status_code == 400
        too_large = await import_csv(client, site_id, device_id, HEADER + "\r\n" + "x" * 1_000_001)
        assert too_large.status_code == 413
