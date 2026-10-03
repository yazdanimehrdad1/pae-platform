"""
Integration tests for /api/device-points.

Guards point CRUD against a real database: bulk upsert by name, category / class /
severity filtering, class and severity stored and changed under the wire name "class",
soft/hard delete and restore, and that the device's scan ranges are recomputed from its
NATIVE points after each write, unless a manual override locked them. Virtual points: created
and updated only through the /virtual routes (never bulk or the generic PUT), their inputs checked
(same site, active, not virtual, a bitfield for bit tests), their storage derived from the kind.
"""

import asyncpg
import pytest
from httpx import AsyncClient

from integration.factories import (
    DEVICE_POINT_LIST,
    create_device,
    create_site,
    create_virtual_point,
    point_request,
    upsert_points,
)
from schemas.api_models import (
    DevicePointResponse,
    DevicePointsBulkRequest,
    DevicePointUpdateRequest,
    DeviceScanRanges,
    DeviceWithPoints,
    LatestResponse,
    RegisterRange,
    VirtualCalculationDefinition,
    VirtualCase,
    VirtualCondition,
    VirtualConditionDefinition,
    VirtualConditionGroup,
    VirtualPointCreateRequest,
    VirtualPointUpdateRequest,
)
from schemas.tests_models import ApiErrorDetail, ApiErrorResponse


def points_url(site_id: int, device_id: int) -> str:
    return f"/api/device-points/site/{site_id}/device/{device_id}"


async def get_device(client: AsyncClient, site_id: int, device_id: int) -> DeviceWithPoints:
    response = await client.get(f"/api/devices/site/{site_id}/devices/{device_id}")
    assert response.status_code == 200, response.text
    return DeviceWithPoints.model_validate(response.json())


async def list_points(
    client: AsyncClient, url: str, **params: str | bool
) -> list[DevicePointResponse]:
    response = await client.get(url, params=params)
    assert response.status_code == 200, response.text
    return DEVICE_POINT_LIST.validate_python(response.json())


async def make_device(client: AsyncClient) -> tuple[int, int]:
    site = await create_site(client)
    device = await create_device(client, site.site_id)
    return site.site_id, device.device_id


def update_body(update: DevicePointUpdateRequest) -> dict[str, object]:
    """Wire body for a partial update: only the fields the test set, under their wire names."""
    return update.model_dump(mode="json", exclude_unset=True, by_alias=True)


class TestBulkUpsert:
    async def test_creates_points_and_recomputes_scan_ranges(self, client):
        site_id, device_id = await make_device(client)
        points = await upsert_points(
            client,
            site_id,
            device_id,
            [
                point_request(name="active_power", address=100, size=2, data_type="float32"),
                point_request(name="state", address=105, size=1, data_type="enum16"),
            ],
        )
        assert {point.name for point in points} == {"active_power", "state"}
        assert all(point.category == "NATIVE" for point in points)

        device = await get_device(client, site_id, device_id)
        # 100-101 and 105 are within MAX_INTER_POINT_GAP, so one range covers both.
        assert device.scan_ranges is not None
        assert device.scan_ranges.holding == [RegisterRange(start_index=100, count=6)]
        assert device.scan_ranges_locked is False

    async def test_existing_name_is_updated_not_duplicated(self, client):
        site_id, device_id = await make_device(client)
        await upsert_points(client, site_id, device_id, [point_request(unit="kW")])
        await upsert_points(client, site_id, device_id, [point_request(unit="MW")])

        listed = await list_points(client, points_url(site_id, device_id))
        assert [(point.name, point.unit) for point in listed] == [("active_power", "MW")]

    async def test_native_point_without_address_is_400(self, client):
        site_id, device_id = await make_device(client)
        body = DevicePointsBulkRequest(points=[point_request(address=None)])
        response = await client.put(
            f"{points_url(site_id, device_id)}/bulk", json=body.model_dump(mode="json")
        )
        assert response.status_code == 400

    async def test_size_not_matching_data_type_is_422(self, client):
        site_id, device_id = await make_device(client)
        # Deliberately invalid: int32 needs 2 registers, so this can't be built as a model.
        bad_point = point_request().model_dump(mode="json") | {"data_type": "int32", "size": 1}
        response = await client.put(
            f"{points_url(site_id, device_id)}/bulk", json={"points": [bad_point]}
        )
        assert response.status_code == 422

    async def test_unknown_device_is_404(self, client):
        site = await create_site(client)
        body = DevicePointsBulkRequest(points=[point_request()])
        response = await client.put(
            f"{points_url(site.site_id, 9999)}/bulk", json=body.model_dump(mode="json")
        )
        assert response.status_code == 404


class TestListPoints:
    async def test_category_filter(self, client):
        site = await create_site(client)
        device = await create_device(client, site.site_id, name="bess-1", type="BESS")
        await upsert_points(client, site.site_id, device.device_id, [point_request()])
        url = points_url(site.site_id, device.device_id)

        native = await list_points(client, url, category="NATIVE")
        assert [point.name for point in native] == ["active_power"]

        standardized = await list_points(client, url, category="STANDARDIZED")
        assert standardized
        assert all(point.category == "STANDARDIZED" for point in standardized)


class TestClassAndSeverity:
    async def test_bulk_create_stores_both_and_returns_class_key(self, client):
        site_id, device_id = await make_device(client)
        body = DevicePointsBulkRequest(
            points=[point_request(point_class="ALARM", severity="HIGH")]
        ).model_dump(mode="json", by_alias=True)
        response = await client.put(f"{points_url(site_id, device_id)}/bulk", json=body)
        assert response.status_code == 200, response.text
        [raw_point] = response.json()
        assert raw_point["class"] == "ALARM"  # the wire name, not point_class
        assert "point_class" not in raw_point
        [point] = DEVICE_POINT_LIST.validate_python(response.json())
        assert (point.point_class, point.severity) == ("ALARM", "HIGH")

    async def test_both_are_optional(self, client):
        site_id, device_id = await make_device(client)
        [point] = await upsert_points(client, site_id, device_id, [point_request()])
        assert point.point_class is None
        assert point.severity is None

    async def test_put_changes_them_and_omitting_keeps_them(self, client):
        site_id, device_id = await make_device(client)
        [point] = await upsert_points(
            client, site_id, device_id, [point_request(point_class="ANALOG", severity="LOW")]
        )
        url = f"{points_url(site_id, device_id)}/{point.id}"

        response = await client.put(url, json=update_body(DevicePointUpdateRequest(point_class="ALARM")))
        assert response.status_code == 200
        updated = DevicePointResponse.model_validate(response.json())
        assert (updated.point_class, updated.severity) == ("ALARM", "LOW")

        response = await client.put(url, json=update_body(DevicePointUpdateRequest(unit="W")))
        kept = DevicePointResponse.model_validate(response.json())
        assert (kept.point_class, kept.severity) == ("ALARM", "LOW")

    async def test_bulk_update_by_name_changes_them(self, client):
        site_id, device_id = await make_device(client)
        await upsert_points(client, site_id, device_id, [point_request(point_class="BINARY")])
        [point] = await upsert_points(
            client, site_id, device_id, [point_request(point_class="CONTROL", severity="MEDIUM")]
        )
        assert (point.point_class, point.severity) == ("CONTROL", "MEDIUM")

    async def test_invalid_values_are_422(self, client):
        site_id, device_id = await make_device(client)
        valid = DevicePointsBulkRequest(points=[point_request()]).model_dump(mode="json", by_alias=True)
        for bad_field in ({"class": "METERING"}, {"severity": "CRITICAL"}):
            payload = {"points": [valid["points"][0] | bad_field]}
            response = await client.put(f"{points_url(site_id, device_id)}/bulk", json=payload)
            assert response.status_code == 422, bad_field

    async def test_list_filters_by_class_and_severity(self, client):
        site_id, device_id = await make_device(client)
        await upsert_points(
            client,
            site_id,
            device_id,
            [
                point_request(name="power", address=100, point_class="ANALOG"),
                point_request(name="trip", address=110, point_class="ALARM", severity="HIGH"),
                point_request(name="warn", address=120, point_class="ALARM", severity="LOW"),
            ],
        )
        url = points_url(site_id, device_id)

        alarms = await list_points(client, url, **{"class": "ALARM"})
        assert sorted(point.name for point in alarms) == ["trip", "warn"]

        high_alarms = await list_points(client, url, **{"class": "ALARM", "severity": "HIGH"})
        assert [point.name for point in high_alarms] == ["trip"]

        low = await list_points(client, url, severity="LOW")
        assert [point.name for point in low] == ["warn"]

    async def test_unknown_filter_value_is_422(self, client):
        site_id, device_id = await make_device(client)
        response = await client.get(points_url(site_id, device_id), params={"class": "METERING"})
        assert response.status_code == 422


class TestUpdatePoint:
    async def test_update_moves_point_and_recomputes_scan_ranges(self, client):
        site_id, device_id = await make_device(client)
        [point] = await upsert_points(client, site_id, device_id, [point_request()])

        response = await client.put(
            f"{points_url(site_id, device_id)}/{point.id}",
            json=update_body(DevicePointUpdateRequest(address=300)),
        )
        assert response.status_code == 200
        assert DevicePointResponse.model_validate(response.json()).address == 300

        device = await get_device(client, site_id, device_id)
        assert device.scan_ranges is not None
        assert device.scan_ranges.holding == [RegisterRange(start_index=300, count=2)]

    async def test_rename_to_existing_name_is_409(self, client):
        site_id, device_id = await make_device(client)
        _, second = await upsert_points(
            client,
            site_id,
            device_id,
            [point_request(name="first", address=100), point_request(name="second", address=200)],
        )
        response = await client.put(
            f"{points_url(site_id, device_id)}/{second.id}",
            json=update_body(DevicePointUpdateRequest(name="first")),
        )
        assert response.status_code == 409

    async def test_unknown_point_is_404(self, client):
        site_id, device_id = await make_device(client)
        response = await client.put(
            f"{points_url(site_id, device_id)}/9999",
            json=update_body(DevicePointUpdateRequest(unit="kW")),
        )
        assert response.status_code == 404


class TestDeleteAndRestorePoints:
    async def test_soft_delete_hides_point_and_restore_brings_it_back(self, client):
        site_id, device_id = await make_device(client)
        [point] = await upsert_points(client, site_id, device_id, [point_request()])
        url = points_url(site_id, device_id)

        deleted = await client.delete(url, params={"point_ids": [point.id]})
        assert deleted.status_code == 200
        assert [item.id for item in DEVICE_POINT_LIST.validate_python(deleted.json())] == [point.id]
        assert await list_points(client, url) == []
        assert [item.id for item in await list_points(client, f"{url}/deleted")] == [point.id]

        restored = await client.post(f"{url}/{point.id}/restore")
        assert restored.status_code == 200
        assert DevicePointResponse.model_validate(restored.json()).deleted_at is None
        assert [item.id for item in await list_points(client, url)] == [point.id]

    async def test_hard_delete_requires_confirm(self, client):
        site_id, device_id = await make_device(client)
        [point] = await upsert_points(client, site_id, device_id, [point_request()])
        response = await client.delete(
            points_url(site_id, device_id), params={"point_ids": [point.id], "mode": "hard"}
        )
        assert response.status_code == 400
        error = ApiErrorResponse.model_validate(response.json())
        assert isinstance(error.detail, ApiErrorDetail)
        assert error.detail.error == "ConfirmationRequired"

    async def test_hard_delete_is_permanent(self, client):
        site_id, device_id = await make_device(client)
        [point] = await upsert_points(client, site_id, device_id, [point_request()])
        url = points_url(site_id, device_id)
        response = await client.delete(
            url, params={"point_ids": [point.id], "mode": "hard", "confirm": True}
        )
        assert response.status_code == 200
        assert await list_points(client, url, include_deleted=True) == []

    async def test_missing_point_ids_are_404(self, client):
        site_id, device_id = await make_device(client)
        response = await client.delete(points_url(site_id, device_id), params={"point_ids": [9999]})
        assert response.status_code == 404


class TestScanRangeOverride:
    async def test_override_locks_ranges_until_reset(self, client):
        site_id, device_id = await make_device(client)
        await upsert_points(client, site_id, device_id, [point_request(address=100, size=2)])
        url = f"{points_url(site_id, device_id)}/scan-ranges"
        manual = DeviceScanRanges(holding=[RegisterRange(start_index=0, count=50)])

        override = await client.put(url, json=manual.model_dump(mode="json"))
        assert override.status_code == 200
        assert DeviceScanRanges.model_validate(override.json()) == manual

        # A point write must not overwrite locked ranges.
        await upsert_points(client, site_id, device_id, [point_request(name="extra", address=400)])
        device = await get_device(client, site_id, device_id)
        assert device.scan_ranges_locked is True
        assert device.scan_ranges == manual

        reset = await client.delete(url)
        assert reset.status_code == 200
        device = await get_device(client, site_id, device_id)
        assert device.scan_ranges_locked is False
        assert device.scan_ranges is not None
        assert device.scan_ranges.holding == [
            RegisterRange(start_index=100, count=2),
            RegisterRange(start_index=400, count=2),
        ]


# --- Virtual points ---------------------------------------------------------------------


def calculation(*inputs: int, function: str = "sum") -> VirtualCalculationDefinition:
    return VirtualCalculationDefinition(kind="calculation", function=function, inputs=list(inputs))


def ready_condition(state_point: int, flags_point: int) -> VirtualConditionDefinition:
    return VirtualConditionDefinition(
        kind="condition",
        cases=[VirtualCase(
            output=1,
            label="ready",
            when=VirtualConditionGroup(match="all", items=[
                VirtualCondition(point_id=state_point, operator="==", value=2),
                VirtualCondition(point_id=flags_point, operator="bit_set", bit=3),
            ]),
        )],
        default_output=0,
        default_label="not ready",
    )


async def two_devices_with_inputs(client: AsyncClient) -> tuple[int, int, list[DevicePointResponse]]:
    """A site with two devices; returns (site_id, first device_id, [power_a, power_b, state, flags])."""
    site = await create_site(client)
    first = await create_device(client, site.site_id, name="meter-a")
    second = await create_device(client, site.site_id, name="meter-b", host="10.0.0.11")
    (power_a,) = await upsert_points(client, site.site_id, first.device_id, [point_request()])
    power_b, state, flags = await upsert_points(client, site.site_id, second.device_id, [
        point_request(),
        point_request(name="state", address=110, size=1, data_type="enum16", enum_detail={"2": "running"}),
        point_request(name="flags", address=111, size=1, data_type="bitfield16", bitfield_detail={"3": "relay"}),
    ])
    return site.site_id, first.device_id, [power_a, power_b, state, flags]


def virtual_url(site_id: int, device_id: int) -> str:
    return f"{points_url(site_id, device_id)}/virtual"


class TestCreateVirtualPoint:
    async def test_calculation_reads_other_devices_and_is_stored_as_float32(self, client):
        site_id, device_id, (power_a, power_b, *_) = await two_devices_with_inputs(client)
        definition = calculation(power_a.id, power_b.id)

        point = await create_virtual_point(client, site_id, device_id, VirtualPointCreateRequest(
            name="SITE_POWER", unit="kW", definition=definition,
        ))

        assert (point.category, point.data_type, point.size, point.address, point.poll_kind) == (
            "VIRTUAL", "float32", 2, 0, None,
        )
        assert point.virtual_definition == definition
        listed = await list_points(client, points_url(site_id, device_id), category="VIRTUAL")
        assert [listed_point.id for listed_point in listed] == [point.id]
        device = await get_device(client, site_id, device_id)
        assert [virtual.name for virtual in device.points.virtual] == ["SITE_POWER"]

    async def test_condition_is_an_enum_labelled_by_its_cases(self, client):
        site_id, device_id, (*_, state, flags) = await two_devices_with_inputs(client)

        point = await create_virtual_point(client, site_id, device_id, VirtualPointCreateRequest(
            name="READY", point_class="BINARY", definition=ready_condition(state.id, flags.id),
        ))

        assert (point.data_type, point.size) == ("enum16", 1)
        assert point.enum_detail == {"0": "not ready", "1": "ready"}
        assert point.point_class == "BINARY"

    async def test_existing_name_is_409(self, client):
        site_id, device_id, (power_a, *_) = await two_devices_with_inputs(client)
        request = VirtualPointCreateRequest(name="active_power", definition=calculation(power_a.id))
        response = await client.post(virtual_url(site_id, device_id), json=request.model_dump(mode="json"))
        assert response.status_code == 409

    async def test_unknown_input_is_400(self, client):
        site_id, device_id, _ = await two_devices_with_inputs(client)
        request = VirtualPointCreateRequest(name="V", definition=calculation(99999))
        response = await client.post(virtual_url(site_id, device_id), json=request.model_dump(mode="json"))
        assert response.status_code == 400
        detail = ApiErrorResponse.model_validate(response.json()).detail
        assert isinstance(detail, ApiErrorDetail) and "99999" in detail.message

    async def test_input_on_another_site_is_400(self, client):
        site_id, device_id, _ = await two_devices_with_inputs(client)
        other_site = await create_site(client, name="Other Site")
        other_device = await create_device(client, other_site.site_id)
        (foreign,) = await upsert_points(client, other_site.site_id, other_device.device_id, [point_request()])
        request = VirtualPointCreateRequest(name="V", definition=calculation(foreign.id))
        response = await client.post(virtual_url(site_id, device_id), json=request.model_dump(mode="json"))
        assert response.status_code == 400

    async def test_virtual_or_deleted_input_is_400(self, client):
        site_id, device_id, (power_a, power_b, *_) = await two_devices_with_inputs(client)
        virtual = await create_virtual_point(client, site_id, device_id, VirtualPointCreateRequest(
            name="V1", definition=calculation(power_a.id),
        ))
        chained = VirtualPointCreateRequest(name="V2", definition=calculation(virtual.id))
        response = await client.post(virtual_url(site_id, device_id), json=chained.model_dump(mode="json"))
        assert response.status_code == 400

        deleted = await client.delete(points_url(site_id, power_b.device_id), params={"point_ids": [power_b.id]})
        assert deleted.status_code == 200
        reads_deleted = VirtualPointCreateRequest(name="V3", definition=calculation(power_b.id))
        response = await client.post(virtual_url(site_id, device_id), json=reads_deleted.model_dump(mode="json"))
        assert response.status_code == 400

    async def test_bit_condition_on_a_non_bitfield_is_400(self, client):
        site_id, device_id, (power_a, _, state, _) = await two_devices_with_inputs(client)
        request = VirtualPointCreateRequest(name="V", definition=ready_condition(state.id, power_a.id))
        response = await client.post(virtual_url(site_id, device_id), json=request.model_dump(mode="json"))
        assert response.status_code == 400

    async def test_malformed_definition_is_422(self, client):
        site_id, device_id, (power_a, *_) = await two_devices_with_inputs(client)
        valid = VirtualPointCreateRequest(name="V", definition=calculation(power_a.id))
        # Deliberately invalid: a ratio needs exactly two inputs.
        bad = valid.model_dump(mode="json") | {
            "definition": {"kind": "calculation", "function": "ratio", "inputs": [power_a.id]}
        }
        response = await client.post(virtual_url(site_id, device_id), json=bad)
        assert response.status_code == 422

    async def test_unknown_device_is_404(self, client):
        site = await create_site(client)
        request = VirtualPointCreateRequest(name="V", definition=calculation(1))
        response = await client.post(virtual_url(site.site_id, 9999), json=request.model_dump(mode="json"))
        assert response.status_code == 404


class TestUpdateVirtualPoint:
    async def test_new_definition_can_change_the_kind(self, client):
        site_id, device_id, (power_a, _, state, flags) = await two_devices_with_inputs(client)
        point = await create_virtual_point(client, site_id, device_id, VirtualPointCreateRequest(
            name="V", unit="kW", definition=calculation(power_a.id),
        ))

        update = VirtualPointUpdateRequest(definition=ready_condition(state.id, flags.id), unit=None)
        response = await client.put(
            f"{virtual_url(site_id, device_id)}/{point.id}",
            json=update.model_dump(mode="json", exclude_unset=True, by_alias=True),
        )

        assert response.status_code == 200, response.text
        updated = DevicePointResponse.model_validate(response.json())
        assert (updated.name, updated.data_type, updated.size, updated.unit) == ("V", "enum16", 1, None)
        assert updated.enum_detail == {"0": "not ready", "1": "ready"}

    async def test_rename_to_existing_name_is_409(self, client):
        site_id, device_id, (power_a, *_) = await two_devices_with_inputs(client)
        point = await create_virtual_point(client, site_id, device_id, VirtualPointCreateRequest(
            name="V", definition=calculation(power_a.id),
        ))
        response = await client.put(
            f"{virtual_url(site_id, device_id)}/{point.id}",
            json=VirtualPointUpdateRequest(name="active_power").model_dump(mode="json", exclude_unset=True),
        )
        assert response.status_code == 409

    async def test_non_virtual_point_is_400_and_unknown_point_is_404(self, client):
        site_id, device_id, (power_a, *_) = await two_devices_with_inputs(client)
        body = VirtualPointUpdateRequest(name="renamed").model_dump(mode="json", exclude_unset=True)
        response = await client.put(f"{virtual_url(site_id, device_id)}/{power_a.id}", json=body)
        assert response.status_code == 400
        response = await client.put(f"{virtual_url(site_id, device_id)}/99999", json=body)
        assert response.status_code == 404


class TestVirtualPointsStayOffTheRegisterRoutes:
    async def test_generic_update_of_a_virtual_point_is_400(self, client):
        site_id, device_id, (power_a, *_) = await two_devices_with_inputs(client)
        point = await create_virtual_point(client, site_id, device_id, VirtualPointCreateRequest(
            name="V", definition=calculation(power_a.id),
        ))
        response = await client.put(
            f"{points_url(site_id, device_id)}/{point.id}",
            json=update_body(DevicePointUpdateRequest(data_type="int16", size=1)),
        )
        assert response.status_code == 400

    async def test_bulk_upsert_of_a_virtual_point_is_400(self, client):
        site_id, device_id = await make_device(client)
        body = DevicePointsBulkRequest(points=[point_request(category="VIRTUAL")])
        response = await client.put(f"{points_url(site_id, device_id)}/bulk", json=body.model_dump(mode="json"))
        assert response.status_code == 400

    async def test_a_stored_definition_that_no_longer_parses_loads_as_none(self, client, db):
        """Edited by hand in SQL into something invalid: the point still lists (definition null)
        and computes nothing, instead of the whole device's point list failing."""
        site_id, device_id, (power_a, *_) = await two_devices_with_inputs(client)
        point = await create_virtual_point(client, site_id, device_id, VirtualPointCreateRequest(
            name="V", definition=calculation(power_a.id),
        ))
        await db.execute(
            """UPDATE device_points SET virtual_definition = '{"kind": "nonsense"}'::jsonb WHERE id = $1""", point.id
        )

        listed = await list_points(client, points_url(site_id, device_id), category="VIRTUAL")
        assert [(listed_point.id, listed_point.virtual_definition) for listed_point in listed] == [(point.id, None)]
        latest = await client.get(
            f"/api/device-point-readings/site/{site_id}/device/{device_id}/latest", params={"point_ids": str(point.id)}
        )
        assert latest.status_code == 200, latest.text
        assert LatestResponse.model_validate(latest.json()).readings[str(point.id)].value is None

    async def test_database_rejects_a_definition_on_a_non_virtual_point(self, client, db):
        _, _, (power_a, *_) = await two_devices_with_inputs(client)
        with pytest.raises(asyncpg.CheckViolationError):
            await db.execute(
                "UPDATE device_points SET virtual_definition = '{}'::jsonb WHERE id = $1", power_a.id
            )
