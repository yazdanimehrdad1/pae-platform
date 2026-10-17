"""Site tools against the fake connectors, called the way the agent loop calls them."""

from typing import cast

from fakes import as_dict, make_ctx, rows

from intelli_gateway.tools.local_provider import LocalToolProvider


class TestGetSiteOverview:
    async def test_devices_topology_and_alarm_counts(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool("get_site_overview", {}, make_ctx(site_id=1))
        content = as_dict(result.content)
        assert [device["name"] for device in rows(content, "devices")] == [
            "INV1",
            "INV2",
            "BESS1",
            "POI",
            "WS1",
        ]
        assert "PV field B -- INV2" in cast(list[str], as_dict(content["topology"])["connections"])
        assert content["active_alarm_events"] == 1
        assert content["active_alarm_points"] == 1

    async def test_flags_devices_that_stopped_reporting(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool("get_site_overview", {}, make_ctx(site_id=2))
        stale = [device["name"] for device in rows(result.content, "devices") if device["stale"]]
        assert stale == ["WTG2"]


class TestListPoints:
    async def test_lists_every_point_with_class_labels_and_guides(
        self, provider: LocalToolProvider
    ) -> None:
        result = await provider.call_tool("list_points", {}, make_ctx(site_id=1))
        content = as_dict(result.content)
        assert content["total_matches"] == 18
        by_name = {row["name"]: row for row in rows(content, "points")}
        assert by_name["INV2.AlarmWord"]["point_class"] == "ALARM"
        assert by_name["INV2.AlarmWord"]["labels"] == "bits"
        assert by_name["INV2.Status"]["labels"] == "enum"
        assert by_name["INV2.Status"]["has_guide"] is True
        assert by_name["POI.Frequency"]["has_guide"] is False

    async def test_filter_and_device(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "list_points", {"filter": "temperature", "device_id": 11}, make_ctx(site_id=1)
        )
        assert [row["name"] for row in rows(result.content, "points")] == ["INV2.CabinetTemp"]

    async def test_only_points_of_the_context_site(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool("list_points", {"filter": "WTG"}, make_ctx(site_id=1))
        assert as_dict(result.content)["total_matches"] == 0


class TestGetPointValues:
    async def test_labels_bits_and_not_found(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "get_point_values",
            {"point_names": ["INV2.Status", "INV2.AlarmWord", "POI.Frequency", "NOPE"]},
            make_ctx(site_id=1),
        )
        content = as_dict(result.content)
        values = {row["name"]: row for row in rows(content, "values")}
        assert values["INV2.Status"]["label"] == "DERATED"
        assert values["INV2.AlarmWord"]["active_bits"] == ["OVER_TEMP"]
        assert values["POI.Frequency"]["unit"] == "Hz"
        assert values["POI.Frequency"]["timestamp"] == "2026-06-15T12:00:00Z"
        assert content["not_found"] == ["NOPE"]

    async def test_stale_values_are_flagged(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "get_point_values", {"point_names": ["WTG2.ActivePower"]}, make_ctx(site_id=2)
        )
        value = rows(result.content, "values")[0]
        assert value["stale"] is True
        assert value["age_s"] == 10800.0

    async def test_rejects_too_many_names(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "get_point_values", {"point_names": [f"P{index}" for index in range(21)]}, make_ctx()
        )
        assert result.is_error


class TestGetPointHistory:
    async def test_measurement_is_summarized(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "get_point_history",
            {
                "point_name": "INV1.ActivePower",
                "start": "2026-06-14T12:00:00+00:00",
                "end": "2026-06-15T12:00:00+00:00",
            },
            make_ctx(site_id=1),
        )
        content = as_dict(result.content)
        assert content["kind"] == "summary"
        assert content["count"] == 289  # 24 h at 5 min, both ends included
        assert len(cast(list[object], content["samples"])) == 12
        assert cast(float, content["min"]) == 0.0  # night
        assert cast(float, content["max"]) > 1000  # day

    async def test_status_point_returns_changes(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "get_point_history",
            {
                "point_name": "INV2.Status",
                "start": "2026-06-14T12:00:00+00:00",
                "end": "2026-06-15T12:00:00+00:00",
            },
            make_ctx(site_id=1),
        )
        content = as_dict(result.content)
        assert content["kind"] == "state_changes"
        assert [row["label"] for row in rows(content, "changes")] == [
            "DERATED",
            "SLEEPING",
            "RUNNING",
            "DERATED",
        ]

    async def test_rejects_too_long_window(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "get_point_history",
            {
                "point_name": "INV1.ActivePower",
                "start": "2026-01-01T00:00:00+00:00",
                "end": "2026-06-01T00:00:00+00:00",
            },
            make_ctx(site_id=1),
        )
        assert result.is_error
        assert "hint" in as_dict(result.content)

    async def test_rejects_end_before_start(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "get_point_history",
            {
                "point_name": "INV1.ActivePower",
                "start": "2026-06-15T00:00:00+00:00",
                "end": "2026-06-14T00:00:00+00:00",
            },
            make_ctx(site_id=1),
        )
        assert result.is_error

    async def test_requires_timezone_in_timestamps(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "get_point_history",
            {
                "point_name": "INV1.ActivePower",
                "start": "2026-06-14T00:00",
                "end": "2026-06-15T00:00",
            },
            make_ctx(site_id=1),
        )
        assert as_dict(result.content)["error"] == "invalid arguments"

    async def test_unknown_point(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "get_point_history",
            {
                "point_name": "NOPE",
                "start": "2026-06-14T00:00:00+00:00",
                "end": "2026-06-15T00:00:00+00:00",
            },
            make_ctx(site_id=1),
        )
        assert result.is_error
        assert as_dict(result.content)["hint"] == "call list_points to see valid names"


class TestGetDeviceStatus:
    async def test_derated_inverter_gets_guidance(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool("get_device_status", {"device_id": 11}, make_ctx())
        content = as_dict(result.content)
        guidance = rows(content, "guidance")
        assert {entry["point"] for entry in guidance} == {
            "INV2.Status",
            "INV2.AlarmWord",
            "INV2.CabinetTemp",
        }
        derated = next(entry for entry in guidance if entry["point"] == "INV2.Status")
        assert derated["label"] == "DERATED"
        assert derated["probable_causes"]
        assert [event["alarm_name"] for event in rows(content, "active_alarm_events")] == [
            "INV2 over-temperature"
        ]

    async def test_healthy_inverter_has_no_guidance(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool("get_device_status", {"device_id": 10}, make_ctx())
        assert rows(result.content, "guidance") == []

    async def test_stale_device(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "get_device_status", {"device_id": 101}, make_ctx(site_id=2)
        )
        assert as_dict(as_dict(result.content)["comms"])["stale"] is True

    async def test_device_of_another_site(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool("get_device_status", {"device_id": 101}, make_ctx())
        assert result.is_error
