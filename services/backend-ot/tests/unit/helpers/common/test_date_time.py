"""
Unit tests for timezone normalization on inbound query bounds.

Guards the invariant that a datetime reaching the DB layer is always aware UTC. A naive
datetime is resolved by asyncpg against the *process* timezone, so an unqualified bound
would silently mean different instants in different environments and return the wrong
window rather than an error.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from helpers.common.date_time import (
    normalize_to_utc,
    parse_iso_datetime,
    resolve_time_range,
    resolve_timezone,
)

PACIFIC = "America/Los_Angeles"


class TestResolveTimezone:
    def test_resolves_iana_name(self):
        assert resolve_timezone(PACIFIC) == ZoneInfo(PACIFIC)

    @pytest.mark.parametrize(
        "typed",
        ["UTC", "utc", "Utc", " utc "],
    )
    def test_utc_is_case_and_whitespace_insensitive(self, typed):
        """ZoneInfo itself only accepts exact 'UTC'; a hand-typed param should not care."""
        assert resolve_timezone(typed) == ZoneInfo("UTC")

    @pytest.mark.parametrize(
        "typed",
        ["America/Los_Angeles", "america/los_angeles", "AMERICA/LOS_ANGELES"],
    )
    def test_region_zone_is_case_insensitive(self, typed):
        assert resolve_timezone(typed) == ZoneInfo(PACIFIC)

    @pytest.mark.parametrize("bad", ["Not/AZone", "XYZ", "", "America/Los Angeles"])
    def test_rejects_unknown_zone(self, bad):
        with pytest.raises(ValueError, match="Unknown timezone"):
            resolve_timezone(bad)

    @pytest.mark.parametrize(
        ("alias", "expected"),
        [
            ("PT", PACIFIC), ("PST", PACIFIC), ("PDT", PACIFIC), ("pdt", PACIFIC),
            ("ET", "America/New_York"), ("EST", "America/New_York"),
            ("CT", "America/Chicago"), ("MT", "America/Denver"),
            ("HST", "Pacific/Honolulu"), ("GMT", "UTC"), ("Z", "UTC"),
        ],
    )
    def test_us_shorthands_resolve(self, alias, expected):
        assert resolve_timezone(alias) == ZoneInfo(expected)

    @pytest.mark.parametrize("alias", ["PST", "PDT", "PT"])
    def test_alias_selects_zone_not_fixed_offset(self, alias):
        """
        The standard/daylight spelling must not pin the offset: 'PDT' in January still
        means Pacific in January, i.e. -08:00. Otherwise an alias would silently return
        data from the wrong hour for half the year.
        """
        zone = resolve_timezone(alias)
        january = datetime(2026, 1, 15, 20, 0, tzinfo=UTC).astimezone(zone)
        july = datetime(2026, 7, 15, 20, 0, tzinfo=UTC).astimezone(zone)
        assert january.utcoffset().total_seconds() == -8 * 3600
        assert july.utcoffset().total_seconds() == -7 * 3600

    def test_alias_and_full_name_are_interchangeable(self):
        naive = datetime(2026, 9, 20, 19, 0)
        assert normalize_to_utc(naive, "start_time", resolve_timezone("PDT")) == normalize_to_utc(
            naive, "start_time", resolve_timezone(PACIFIC)
        )

    def test_observes_dst_transition(self):
        """The concrete reason local time is not stored: the offset is not constant."""
        pacific = resolve_timezone(PACIFIC)
        january = datetime(2026, 1, 15, 12, 0, tzinfo=UTC).astimezone(pacific)
        july = datetime(2026, 7, 15, 12, 0, tzinfo=UTC).astimezone(pacific)
        assert january.utcoffset().total_seconds() == -8 * 3600  # PST
        assert july.utcoffset().total_seconds() == -7 * 3600  # PDT


class TestNormalizeToUtc:
    def test_aware_utc_passes_through(self):
        value = datetime(2026, 9, 21, 2, 0, tzinfo=UTC)
        assert normalize_to_utc(value, "start_time", None) == value

    def test_aware_offset_converts_to_utc(self):
        pacific = ZoneInfo(PACIFIC)
        value = datetime(2026, 9, 20, 19, 0, tzinfo=pacific)  # 7pm PDT
        assert normalize_to_utc(value, "start_time", None) == datetime(2026, 9, 21, 2, 0, tzinfo=UTC)

    def test_explicit_offset_wins_over_tz(self):
        """An offset is already unambiguous; tz must not re-interpret it."""
        value = datetime(2026, 9, 21, 2, 0, tzinfo=UTC)
        result = normalize_to_utc(value, "start_time", ZoneInfo("America/New_York"))
        assert result == datetime(2026, 9, 21, 2, 0, tzinfo=UTC)

    def test_naive_with_tz_is_read_as_local_wall_clock(self):
        value = datetime(2026, 9, 20, 19, 0)  # naive "7pm"
        result = normalize_to_utc(value, "start_time", ZoneInfo(PACIFIC))
        assert result == datetime(2026, 9, 21, 2, 0, tzinfo=UTC)

    def test_naive_without_tz_is_rejected(self):
        with pytest.raises(ValueError) as err:
            normalize_to_utc(datetime(2026, 9, 20, 19, 0), "start_time", None)
        message = str(err.value)
        assert "start_time" in message
        assert "tz=" in message

    def test_error_names_the_offending_field(self):
        with pytest.raises(ValueError, match="end_time"):
            normalize_to_utc(datetime(2026, 9, 20, 19, 0), "end_time", None)

    def test_result_is_always_aware(self):
        for value, tz in [
            (datetime(2026, 9, 21, 2, 0, tzinfo=UTC), None),
            (datetime(2026, 9, 20, 19, 0), ZoneInfo(PACIFIC)),
        ]:
            assert normalize_to_utc(value, "start_time", tz).tzinfo is not None

    def test_dst_fall_back_ambiguity_picks_earlier_instant(self):
        """2026-11-01 01:30 Pacific happens twice; fold=0 selects the first (PDT)."""
        ambiguous = datetime(2026, 11, 1, 1, 30)
        result = normalize_to_utc(ambiguous, "start_time", ZoneInfo(PACIFIC))
        assert result == datetime(2026, 11, 1, 8, 30, tzinfo=UTC)


class TestExistingHelpersStayAware:
    def test_resolve_time_range_returns_aware_utc(self):
        start, end = resolve_time_range("1H")
        assert start.tzinfo is not None and end.tzinfo is not None
        assert (end - start).total_seconds() == 3600

    def test_parse_iso_datetime_z_is_aware_bare_is_naive(self):
        """The asymmetry the middleware must not compare across."""
        assert parse_iso_datetime("2026-09-21T02:00:00Z").tzinfo is not None
        assert parse_iso_datetime("2026-09-21T02:00:00").tzinfo is None
        assert parse_iso_datetime("nonsense") is None
