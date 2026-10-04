"""Shared fixtures: the shipped defaults and profiles in site_config/ (read-only), a writable
copy of it, and a builder for synthetic site configs."""

import shutil
from pathlib import Path
from typing import Any

import pytest

from powerflow.point_standard import PointStandard, load_point_standard
from powerflow.points.modbus_map import ModbusMap
from powerflow.settings import SERVICE_ROOT as POWERFLOW_ROOT
from powerflow.settings import settings
from powerflow.site_config import SiteConfig
from powerflow.storage import ProfileStore
from powerflow.storage.defaults import read_defaults

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SITE_CONFIG_DIR = SERVICE_ROOT / "site_config"
# Read-only use only: tests that write profiles get a copy (the `site_config_copy` fixture).
DEFAULTS = read_defaults(SITE_CONFIG_DIR)
DEFAULT_SITE_NAMES = [site.name for site in DEFAULTS.sites]
PROFILES = ProfileStore(SITE_CONFIG_DIR / "profiles")
POINT_STANDARD: PointStandard = load_point_standard(POWERFLOW_ROOT / "docs" / "point-standard")


def default_site(name: str) -> SiteConfig:
    return next(site.config for site in DEFAULTS.sites if site.name == name)


def default_site_maps(name: str) -> dict[str, ModbusMap]:
    return next(site.maps for site in DEFAULTS.sites if site.name == name)


TRANSFORMER_2750: dict[str, Any] = {
    "s_rated_kva": 2750,
    "vn_hv_kv": 12.47,
    "vn_lv_kv": 0.69,
    "z_pct": 5.75,
    "x_r": 7.0,
}


def bess_entry(asset_id: str, **battery: float) -> dict[str, Any]:
    return {
        "id": asset_id,
        "inverter": {
            "s_rated_kva": 2750,
            "p_discharge_max_kw": 2500,
            "p_charge_max_kw": 2500,
            "v_lv_kv": 0.69,
        },
        "battery": {"capacity_kwh": 10000, "soc_initial_pct": 50, **battery},
        "transformer": TRANSFORMER_2750,
    }


def pv_entry(asset_id: str) -> dict[str, Any]:
    return {
        "id": asset_id,
        "dc_kwp": 3250,
        "inverter": {"s_rated_kva": 2750, "p_max_kw": 2500, "v_lv_kv": 0.69},
        "availability": {"source": "ac_kw", "scenario": "clear_sky_high", "scale": 0.5},
        "transformer": TRANSFORMER_2750,
    }


def site_config_dict(n_bess: int = 1, n_pv: int = 1, n_loads: int = 1) -> dict[str, Any]:
    """A valid test-mode config with N identical BESS and PV on one collector."""
    return {
        "schema_version": 1,
        "simulation": {
            "start_time": "2026-06-21T12:00:00Z",
            "autostart": False,
            "test_mode": True,
            "seed": 3,
        },
        "bess": [bess_entry(f"bess{index + 1}") for index in range(n_bess)],
        "pv": [pv_entry(f"pv{index + 1}") for index in range(n_pv)],
        "loads": [
            {"id": f"load{index + 1}", "profile": {"scenario": "typical"}}
            for index in range(n_loads)
        ],
    }


def make_site_config(n_bess: int = 1, n_pv: int = 1, n_loads: int = 1) -> SiteConfig:
    return SiteConfig.model_validate(site_config_dict(n_bess, n_pv, n_loads))


@pytest.fixture(autouse=True)
def modbus_on_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apps started in tests (the reference site enables Modbus) listen on an ephemeral
    loopback port, never on 502."""
    monkeypatch.setattr(settings, "modbus_host", "127.0.0.1")
    monkeypatch.setattr(settings, "modbus_port", 0)


@pytest.fixture
def site_config_copy(tmp_path: Path) -> Path:
    """A writable copy of site_config/, so tests never write the repo."""
    copy = tmp_path / "site_config"
    shutil.copytree(SITE_CONFIG_DIR, copy)
    return copy
