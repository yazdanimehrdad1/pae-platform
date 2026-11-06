"""
Unit tests for site_profiles.individual_sites.powerflow_2bess_1pv.powerflow_2bess_1pv_helper_functions.

Guards the pure decisions behind the site's alarms: which status codes and bits make a unit
faulted or derated (and which must not: grid bits, SoC and comms warnings, curtailment, a PV
over-temperature that already tripped), the voltage, frequency, loading and PV performance
arithmetic and its edges, and which devices count as lost.
"""

from datetime import UTC, datetime, timedelta

import pytest

from schemas.site_profiles.individual_sites.powerflow_2bess_1pv import LatestPointValue
from site_profiles.individual_sites.powerflow_2bess_1pv.powerflow_2bess_1pv_helper_functions import (
    BESS_EVT1_FAULT_BITS,
    BESS_EVT1_WARNING_BITS,
    INV_STATE_FAULT,
    INV_STATE_RUNNING,
    bess_warnings,
    frequency_outside,
    inverter_faulted,
    loading_pct,
    pv_derate_reasons,
    pv_performance_pct,
    pv_underperforming,
    set_bits,
    stale_device_ids,
    worst_voltage_deviation_pct,
)

NOW = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)


def code(value: int) -> LatestPointValue:
    return LatestPointValue(value=float(value))


def bits(*labels: str) -> LatestPointValue:
    return LatestPointValue(value=1.0 if labels else 0.0, bits=frozenset(labels))


class TestSetBits:
    def test_set_bits_by_label(self):
        assert set_bits(0b101, {"0": "A", "1": "B", "2": "C"}) == {"A", "C"}

    def test_point_without_labels_has_none(self):
        assert set_bits(7, None) == frozenset()


class TestInverterFaulted:
    def test_fault_state_is_a_fault(self):
        assert inverter_faulted(code(INV_STATE_FAULT), bits())

    def test_own_breaker_open_is_a_fault(self):
        assert inverter_faulted(code(INV_STATE_RUNNING), bits("AC_DISCONNECT"))

    @pytest.mark.parametrize("label", sorted(BESS_EVT1_FAULT_BITS))
    def test_battery_fault_bit_is_a_fault(self, label: str):
        assert inverter_faulted(code(INV_STATE_RUNNING), bits(), bits(label))

    @pytest.mark.parametrize("label", ["GRID_DISCONNECT", "OVER_FREQUENCY", "AC_UNDER_VOLT", "OVER_TEMP"])
    def test_grid_and_shared_alrm_bits_are_not(self, label: str):
        assert not inverter_faulted(code(INV_STATE_RUNNING), bits(label))

    def test_battery_warning_bits_are_not(self):
        assert not inverter_faulted(code(INV_STATE_RUNNING), bits(), bits(*BESS_EVT1_WARNING_BITS))

    def test_nothing_known_is_not(self):
        assert not inverter_faulted(None, None, None)


class TestBessWarnings:
    def test_only_warning_bits_count(self):
        evt1 = bits("FAN_ERROR", "OVER_TEMP_ALARM", "UNDER_SOC_MIN_WARNING", "COMMUNICATION_ERROR")
        assert bess_warnings(evt1) == {"FAN_ERROR"}

    def test_fault_and_warning_sets_dont_overlap(self):
        assert not BESS_EVT1_FAULT_BITS & BESS_EVT1_WARNING_BITS

    def test_missing_word_has_none(self):
        assert bess_warnings(None) == frozenset()


class TestPvDerateReasons:
    def test_fuse_overtemp_and_derated_throttle_count(self):
        reasons = pv_derate_reasons(code(INV_STATE_RUNNING), bits("BLOWN_STRING_FUSE", "OVER_TEMP"), bits("DERATED"))
        assert reasons == {"BLOWN_STRING_FUSE", "OVER_TEMP", "DERATED"}

    def test_overtemp_that_tripped_is_the_fault_not_a_derate(self):
        assert pv_derate_reasons(code(INV_STATE_FAULT), bits("OVER_TEMP"), bits()) == frozenset()

    def test_curtailment_and_clipping_dont_count(self):
        assert pv_derate_reasons(code(INV_STATE_RUNNING), bits(), bits("FIXED_W", "MAX_W")) == frozenset()


class TestWorstVoltageDeviation:
    def test_signed_deviation_of_the_furthest_phase(self):
        assert worst_voltage_deviation_pct([12.47, 13.0, 11.0], 12.47) == pytest.approx((11.0 / 12.47 - 1) * 100)

    def test_no_voltages_is_unknown(self):
        assert worst_voltage_deviation_pct([], 12.47) is None


class TestFrequencyOutside:
    @pytest.mark.parametrize(("hz", "outside"), [(59.29, True), (59.3, False), (60.0, False), (60.5, False), (60.51, True)])
    def test_limits_are_inside(self, hz: float, outside: bool):
        assert frequency_outside(hz, 59.3, 60.5) is outside


class TestLoadingPct:
    def test_either_direction(self):
        assert loading_pct(-2750.0, 2750.0) == loading_pct(2750.0, 2750.0) == 100.0


class TestPvPerformance:
    def test_share_of_available(self):
        assert pv_performance_pct(3000.0, 4000.0, 5000.0, 5.0) == 75.0

    def test_too_little_sun_is_unknown(self):
        assert pv_performance_pct(0.0, 249.0, 5000.0, 5.0) is None
        assert pv_performance_pct(0.0, 250.0, 5000.0, 5.0) == 0.0

    def test_underperforming_only_when_running_unthrottled_and_below(self):
        assert pv_underperforming(code(INV_STATE_RUNNING), bits(), 79.0, 80.0)
        assert not pv_underperforming(code(INV_STATE_RUNNING), bits(), 80.0, 80.0)
        assert not pv_underperforming(code(INV_STATE_RUNNING), bits("FIXED_W"), 50.0, 80.0)
        assert not pv_underperforming(code(4), bits(), 50.0, 80.0)  # THROTTLED
        assert not pv_underperforming(code(INV_STATE_RUNNING), None, 50.0, 80.0)
        assert not pv_underperforming(code(INV_STATE_RUNNING), bits(), None, 80.0)


class TestStaleDeviceIds:
    def test_older_than_the_limit_is_stale(self):
        last = {1: NOW - timedelta(seconds=61), 2: NOW - timedelta(seconds=60), 3: NOW}
        assert stale_device_ids(last, NOW, timedelta(seconds=60)) == [1]

    def test_never_reported_isnt_stale(self):
        assert stale_device_ids({}, NOW, timedelta(seconds=60)) == []
