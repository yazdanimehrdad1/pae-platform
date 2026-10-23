"""Alarm tools against the fake connector."""

from fakes import as_dict, make_ctx, rows

from intelli_gateway.tools.local_provider import LocalToolProvider


class TestGetActiveAlarms:
    async def test_events_and_alarm_points(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool("get_active_alarms", {}, make_ctx(site_id=1))
        events = rows(result.content, "events")
        assert [(e["alarm_name"], e["severity"], e["device_name"]) for e in events] == [
            ("INV2 over-temperature", "warning", "INV2")
        ]
        assert "cleared_at" not in events[0]
        point = rows(result.content, "point_alarms")[0]
        assert point["point_name"] == "INV2.AlarmWord"
        assert point["active_bits"] == ["OVER_TEMP"]

    async def test_comms_loss_on_the_wind_site(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool("get_active_alarms", {}, make_ctx(site_id=2))
        events = rows(result.content, "events")
        assert [(e["alarm_name"], e["severity"]) for e in events] == [
            ("WTG2 communication lost", "fault")
        ]


class TestGetAlarmHistory:
    async def test_timeline_with_durations(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "get_alarm_history",
            {"start": "2026-06-12T12:00:00+00:00", "end": "2026-06-15T12:00:00+00:00"},
            make_ctx(site_id=1),
        )
        content = as_dict(result.content)
        events = rows(content, "events")
        assert content["total_events"] == len(events) == 5
        ws1 = next(e for e in events if e["alarm_name"] == "WS1 communication lost")
        assert ws1["duration_min"] == 42

    async def test_device_filter(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "get_alarm_history",
            {
                "start": "2026-06-12T12:00:00+00:00",
                "end": "2026-06-15T12:00:00+00:00",
                "device_id": 40,
            },
            make_ctx(site_id=1),
        )
        assert [e["alarm_name"] for e in rows(result.content, "events")] == [
            "WS1 communication lost"
        ]

    async def test_rejects_too_long_window(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "get_alarm_history",
            {"start": "2026-01-01T00:00:00+00:00", "end": "2026-06-15T00:00:00+00:00"},
            make_ctx(site_id=1),
        )
        assert result.is_error
