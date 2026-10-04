"""The site config schema accepts the default sites and rejects inconsistent ones."""

import copy
from typing import Any

import pytest
from conftest import DEFAULT_ACTIVE_SITE, DEFAULT_SITE_NAMES, default_site, site_config_dict
from pydantic import ValidationError

from powerflow.site_config import SiteConfig


@pytest.mark.parametrize("name", DEFAULT_SITE_NAMES)
def test_default_sites_validate(name: str) -> None:
    assert default_site(name).schema_version == 1


def test_default_active_site_exists() -> None:
    assert DEFAULT_ACTIVE_SITE in DEFAULT_SITE_NAMES


def test_reference_site_matches_the_spec() -> None:
    config = default_site("2bess_1pv")
    assert config.grid.vn_kv == 12.47 and config.grid.sc_mva == 100 and config.grid.x_r == 5
    assert [bess.inverter.p_discharge_max_kw for bess in config.bess] == [2500, 2500]
    assert [bess.battery.capacity_kwh for bess in config.bess] == [10000, 10000]
    assert all(bess.transformer.z_pct == 5.75 for bess in config.bess)
    assert all(bess.transformer.s_rated_kva == 2750 for bess in config.bess)
    assert config.pv[0].inverter.p_max_kw == 5000 and config.pv[0].transformer.s_rated_kva == 5500
    assert all(asset.transformer.vn_lv_kv == 0.48 for asset in [*config.bess, *config.pv])
    assert {meter.id: meter.transformer for meter in config.meters} == {
        "m_bess1": "bess1",
        "m_bess2": "bess2",
        "m_pv1": "pv1",
    }


def test_defaults_fill_in() -> None:
    config = SiteConfig.model_validate({})
    assert config.grid.vn_kv == 12.47
    assert [collector.id for collector in config.collectors] == ["mv1"]
    assert config.simulation.step_s == 1.0


def test_round_trip_efficiency_splits_evenly() -> None:
    raw = site_config_dict()
    raw["bess"][0]["battery"]["efficiency"] = {"round_trip": 0.81}
    config = SiteConfig.model_validate(raw)
    efficiency = config.bess[0].battery.efficiency
    assert efficiency.eta_charge == pytest.approx(0.9)
    assert efficiency.eta_discharge == pytest.approx(0.9)


def mutate(path: list[str | int], value: Any) -> dict[str, Any]:
    raw = copy.deepcopy(site_config_dict(n_bess=2))
    target: Any = raw
    for key in path[:-1]:
        if isinstance(key, str):
            target = target.setdefault(key, {})
        else:
            target = target[key]
    target[path[-1]] = value
    return raw


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (["bess", 1, "id"], "bess1", "unique"),
        (["bess", 0, "collector"], "nope", "unknown collector"),
        (["loads", 0, "bus"], "nope", "unknown bus"),
        (["bess", 0, "transformer", "vn_hv_kv"], 13.8, "vn_hv_kv"),
        (["bess", 0, "transformer", "vn_lv_kv"], 0.48, "vn_lv_kv"),
        (["bess", 0, "battery", "soc_initial_pct"], 99, "soc_initial_pct"),
        (["bess", 0, "battery", "soc_min_pct"], 96, "soc_min_pct"),
        (["bess", 0, "inverter", "s_rated_kva"], 2000, "s_rated_kva"),
        (["bess", 0, "battery", "efficiency"], {"charge": 0.9}, "discharge"),
        (
            ["bess", 0, "battery", "efficiency"],
            {"charge": 0.9, "discharge": 0.9, "round_trip": 0.8},
            "not both",
        ),
        (["bess", 0, "unexpected"], 1, "Extra inputs"),
        (["grid", "sc_mva"], 0, "greater than 0"),
        (["schema_version"], 2, "schema_version"),
    ],
)
def test_invalid_configs_are_rejected(path: list[str | int], value: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        SiteConfig.model_validate(mutate(path, value))


@pytest.mark.parametrize(
    ("meters", "message"),
    [
        ([{"id": "m1", "transformer": "nope"}], "not a BESS, PV or load with a transformer"),
        ([{"id": "m1", "transformer": "load1"}], "not a BESS, PV or load with a transformer"),
        (
            [{"id": "m1", "transformer": "bess1"}, {"id": "m1", "transformer": "bess2"}],
            "meter ids must be unique",
        ),
        (
            [{"id": "m1", "transformer": "bess1"}, {"id": "m2", "transformer": "bess1"}],
            "already has a meter",
        ),
        ([{"id": "m:1", "transformer": "bess1"}], "pattern"),
    ],
)
def test_invalid_meters_are_rejected(meters: list[dict[str, str]], message: str) -> None:
    raw = site_config_dict(n_bess=2)
    raw["meters"] = meters
    with pytest.raises(ValidationError, match=message):
        SiteConfig.model_validate(raw)


def test_a_load_transformer_can_be_metered() -> None:
    raw = site_config_dict()
    raw["loads"][0]["transformer"] = raw["bess"][0]["transformer"]
    raw["meters"] = [{"id": "m_load1", "transformer": "load1"}]
    assert SiteConfig.model_validate(raw).meters[0].transformer == "load1"


@pytest.mark.parametrize("scenario", ["../typical", "Typical", "a/b", ""])
def test_scenario_names_are_restricted(scenario: str) -> None:
    raw = site_config_dict()
    raw["loads"][0]["profile"]["scenario"] = scenario
    with pytest.raises(ValidationError, match="scenario"):
        SiteConfig.model_validate(raw)
