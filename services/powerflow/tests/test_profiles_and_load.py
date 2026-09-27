"""Profiles: CSV parsing, interpolation, looping, the stored scenarios. Load model: seeded noise."""

from datetime import UTC, datetime

import numpy as np
import pytest
from conftest import PROFILES

from powerflow.errors import ProfileError
from powerflow.models.load import load_output
from powerflow.profiles import Profile, ProfileKind, load_profile_file, parse_profile_csv
from powerflow.site_config.models import NoiseConfig
from powerflow.storage import ProfileFolder

CSV = """timestamp,p_kw,q_kvar
2026-06-21T00:00:00Z,100,10
2026-06-21T00:10:00Z,200,20
2026-06-21T00:20:00Z,400,40
"""
T0 = datetime(2026, 6, 21, tzinfo=UTC).timestamp()


def test_linear_interpolation() -> None:
    profile = parse_profile_csv(CSV, ProfileKind.LOAD, loop=False)
    assert profile.value_at("p_kw", T0) == 100
    assert profile.value_at("p_kw", T0 + 300) == pytest.approx(150)
    assert profile.value_at("q_kvar", T0 + 900) == pytest.approx(30)


def test_hold_ends_without_loop() -> None:
    profile = parse_profile_csv(CSV, ProfileKind.LOAD, loop=False)
    assert profile.value_at("p_kw", T0 - 1000) == 100
    assert profile.value_at("p_kw", T0 + 99_999) == 400


def test_loop_wraps_back_through_the_first_sample() -> None:
    profile = parse_profile_csv(CSV, ProfileKind.LOAD, loop=True)
    assert profile.period_s == 1800  # 20 min span + one 10 min interval
    # Halfway from the last sample (400) back to the first (100).
    assert profile.value_at("p_kw", T0 + 1500) == pytest.approx(250)
    assert profile.value_at("p_kw", T0 + 1800 + 300) == pytest.approx(150)
    assert profile.value_at("p_kw", T0 - 1800 + 300) == pytest.approx(150)


def test_scale() -> None:
    profile = parse_profile_csv(CSV, ProfileKind.LOAD, loop=False, scale=2)
    assert profile.value_at("p_kw", T0) == 200


def test_pf_column_becomes_q() -> None:
    text = "timestamp,p_kw,pf\n2026-06-21T00:00:00Z,1000,0.8\n2026-06-21T00:01:00Z,1000,-0.8\n"
    profile = parse_profile_csv(text, ProfileKind.LOAD, loop=False)
    assert profile.value_at("q_kvar", T0) == pytest.approx(750)
    assert profile.value_at("q_kvar", T0 + 60) == pytest.approx(-750)


def test_unsorted_rows_are_sorted() -> None:
    lines = CSV.strip().splitlines()
    text = "\n".join([lines[0], lines[3], lines[1], lines[2]])
    profile = parse_profile_csv(text, ProfileKind.LOAD, loop=False)
    assert profile.value_at("p_kw", T0 + 300) == pytest.approx(150)


@pytest.mark.parametrize(
    ("text", "kind", "message"),
    [
        ("timestamp,q_kvar\n2026-06-21T00:00:00Z,1\n", ProfileKind.LOAD, "missing column"),
        ("timestamp,p_kw\n2026-06-21T00:00:00Z,1\n", ProfileKind.PV_IRRADIANCE, "ghi_wm2"),
        ("timestamp,p_kw\nnot-a-time,1\n", ProfileKind.PV_AC, "bad timestamp"),
        ("timestamp,p_kw\n2026-06-21T00:00:00Z,abc\n", ProfileKind.PV_AC, "non-numeric"),
        ("timestamp,p_kw\n", ProfileKind.PV_AC, "no rows"),
        ("", ProfileKind.PV_AC, "can't parse"),
        (
            "timestamp,p_kw\n2026-06-21T00:00:00Z,1\n2026-06-21T00:00:00Z,2\n",
            ProfileKind.PV_AC,
            "duplicate",
        ),
    ],
)
def test_bad_csv_is_rejected(text: str, kind: ProfileKind, message: str) -> None:
    with pytest.raises(ProfileError, match=message):
        parse_profile_csv(text, kind, loop=False)


def scenario(folder: ProfileFolder, name: str, kind: ProfileKind) -> Profile:
    return load_profile_file(PROFILES.profile_path(folder, name), kind, True, 1.0)


def peak(profile: Profile, column: str = "p_kw") -> float:
    return float(max(profile.columns[column]))


class TestScenarios:
    LOAD = ["typical", "high_demand", "low_demand", "evening_peak", "flat_industrial"]
    PV = ["clear_sky_high", "overcast_low", "cloudy_dynamic", "clipping_heavy"]

    def test_all_scenarios_exist_and_parse(self) -> None:
        assert PROFILES.list_profiles(ProfileFolder.LOAD) == sorted(self.LOAD)
        assert PROFILES.list_profiles(ProfileFolder.PV) == sorted(self.PV)
        for name in self.LOAD:
            assert scenario(ProfileFolder.LOAD, name, ProfileKind.LOAD).period_s == 86_400
        for name in self.PV:
            for kind in (ProfileKind.PV_AC, ProfileKind.PV_IRRADIANCE):
                profile = scenario(ProfileFolder.PV, name, kind)
                assert profile.value_at(next(iter(profile.columns)), T0) == 0  # midnight

    def test_load_scenarios_differ_as_named(self) -> None:
        def load_peak(name: str) -> float:
            return peak(scenario(ProfileFolder.LOAD, name, ProfileKind.LOAD))

        assert load_peak("high_demand") == pytest.approx(3000, rel=0.01)
        assert load_peak("low_demand") < load_peak("typical") < load_peak("high_demand")

    def test_pv_scenarios_differ_as_named(self) -> None:
        def pv_peak(name: str) -> float:
            return peak(scenario(ProfileFolder.PV, name, ProfileKind.PV_AC))

        assert pv_peak("clipping_heavy") > 5000  # above a 5 MWac inverter
        assert pv_peak("overcast_low") < 0.3 * pv_peak("clear_sky_high")

    def test_cloudy_day_ramps_fast(self) -> None:
        values = scenario(ProfileFolder.PV, "cloudy_dynamic", ProfileKind.PV_AC).columns["p_kw"]
        biggest_ramp = float(np.max(np.abs(np.diff(values))))
        assert biggest_ramp > 0.3 * float(np.max(values))  # > 30 % of peak in one minute


class TestLoadNoise:
    def test_no_noise_passes_through(self) -> None:
        output = load_output(1000, 300, None, np.random.default_rng(0))
        assert (output.p_kw, output.q_kvar) == (1000, 300)

    def test_seeded_noise_is_deterministic(self) -> None:
        noise = NoiseConfig(p_std_pct=2, q_std_pct=2)
        first = load_output(1000, 300, noise, np.random.default_rng((5, 17)))
        second = load_output(1000, 300, noise, np.random.default_rng((5, 17)))
        assert first == second
        assert first.p_kw != 1000

    def test_noise_has_the_configured_spread(self) -> None:
        noise = NoiseConfig(p_std_pct=2, q_std_pct=0)
        rng = np.random.default_rng(1)
        samples = [load_output(1000, 300, noise, rng).p_kw for _ in range(5000)]
        assert np.std(samples) == pytest.approx(20, rel=0.1)
        assert np.mean(samples) == pytest.approx(1000, rel=0.005)
