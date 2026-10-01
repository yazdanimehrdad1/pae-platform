"""
Unit tests for helpers.alarms.events.build_log.

Guards the event log the page shows: one 'raised' entry per event and one 'cleared' entry per
cleared event, each only if it falls within the window, newest first, with the event's message
for a raise and '<alarm name> cleared' for a clear.
"""

from datetime import UTC, datetime, timedelta

from helpers.alarms.events import build_log
from schemas.api_models.alarms import AlarmEventResponse

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def event(event_id: int, raised_hours_ago: float, cleared_hours_ago: float | None) -> AlarmEventResponse:
    return AlarmEventResponse(
        id=event_id, definition_id=10, site_id=1, device_id=None, severity="warning",
        raised_at=NOW - timedelta(hours=raised_hours_ago),
        cleared_at=None if cleared_hours_ago is None else NOW - timedelta(hours=cleared_hours_ago),
        message="Too hot",
    )


class TestBuildLog:
    def test_raises_and_clears_in_the_window_newest_first(self):
        log = build_log([event(1, 3, 1), event(2, 0.5, None), event(3, 8, 2)], {10: "too_hot"}, NOW - timedelta(hours=6))
        assert [(entry.id, entry.kind, entry.message) for entry in log] == [
            ("2:raised", "raised", "Too hot"),
            ("1:cleared", "cleared", "too_hot cleared"),
            ("3:cleared", "cleared", "too_hot cleared"),  # raised 8 h ago: only its clear is in the window
            ("1:raised", "raised", "Too hot"),
        ]

    def test_unknown_alarm_name_falls_back_to_its_id(self):
        (raised, cleared) = sorted(build_log([event(1, 2, 1)], {}, NOW - timedelta(hours=6)), key=lambda e: e.kind, reverse=True)
        assert cleared.message == "alarm 10 cleared"
