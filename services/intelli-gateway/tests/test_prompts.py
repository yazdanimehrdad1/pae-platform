"""The user turn tells the model the current time in UTC and at the site."""

from datetime import UTC, datetime

from intelli_gateway.prompts.system import render_user_turn


class TestRenderUserTurn:
    def test_local_date_differs_from_utc_after_local_midnight(self) -> None:
        # 22:30 UTC on 14 Oct is already 00:30 on 15 Oct in Berlin (CEST): the case the model
        # got wrong when it only saw the UTC timestamp.
        turn = render_user_turn("q", datetime(2026, 10, 14, 22, 30, tzinfo=UTC), "Europe/Berlin")
        assert "Current time (UTC): 2026-10-14T22:30:00+00:00" in turn
        assert "Site local time (Europe/Berlin, UTC+02:00): Thursday 2026-10-15 00:30." in turn
        assert "Yesterday at the site was Wednesday 2026-10-14." in turn
        assert turn.endswith("\n\nq")

    def test_winter_offset(self) -> None:
        turn = render_user_turn("q", datetime(2026, 1, 15, 12, 0, tzinfo=UTC), "Europe/Berlin")
        assert "UTC+01:00): Thursday 2026-01-15 13:00." in turn

    def test_unknown_time_zone_falls_back_to_utc(self) -> None:
        turn = render_user_turn("q", datetime(2026, 10, 14, 22, 30, tzinfo=UTC), "Mars/Base")
        assert "Site time zone 'Mars/Base' is unknown; use UTC dates." in turn
        assert "Current time (UTC): 2026-10-14T22:30:00+00:00" in turn
