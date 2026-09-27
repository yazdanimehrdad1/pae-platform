"""Network builder + pandapower solver: hand calculation, power balance, scaling, divergence."""

import math

import pytest
from conftest import TRANSFORMER_2750, default_site, make_site_config

from powerflow.errors import NonConvergenceError
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.network.solver import Injection
from powerflow.network.topology import (
    GRID_IMPEDANCE,
    POI_LINE,
    InjectionKind,
    PoiBranchKind,
    bess_injection,
    build_topology,
    grid_impedance_ohm,
    load_injection,
    lv_bus,
    pv_injection,
    transformer_name,
)
from powerflow.site_config import SiteConfig


class TestTopology:
    def test_grid_impedance_from_short_circuit_power(self) -> None:
        r_ohm, x_ohm = grid_impedance_ohm(12.47, 100, 5)
        assert math.hypot(r_ohm, x_ohm) == pytest.approx(12.47**2 / 100)
        assert x_ohm / r_ohm == pytest.approx(5)

    def test_poi_branch_without_and_with_poi_line(self) -> None:
        plain = build_topology(make_site_config())
        assert (plain.poi_branch, plain.poi_branch_kind) == (
            GRID_IMPEDANCE,
            PoiBranchKind.IMPEDANCE,
        )
        reference = build_topology(default_site("reference_2bess_1pv"))
        assert (reference.poi_branch, reference.poi_branch_kind) == (POI_LINE, PoiBranchKind.LINE)

    def test_each_asset_gets_lv_bus_transformer_and_injection(self) -> None:
        topology = build_topology(make_site_config(n_bess=2, n_pv=1))
        names = {injection.name: injection for injection in topology.injections}
        for asset in ("bess1", "bess2", "pv1"):
            assert topology.bus(lv_bus(asset)).vn_kv == 0.69
            assert any(tx.name == transformer_name(asset) for tx in topology.transformers)
        assert names[bess_injection("bess1")].kind is InjectionKind.GENERATOR
        assert names[pv_injection("pv1")].kind is InjectionKind.GENERATOR
        assert names[load_injection("load1")].kind is InjectionKind.LOAD


def single_transformer_site(sc_mva: float) -> SiteConfig:
    """Grid → POI → 2750 kVA, 5.75 %Z, X/R 7 transformer → load at 690 V. Nothing else."""
    return SiteConfig.model_validate(
        {
            "grid": {"vn_kv": 12.47, "sc_mva": sc_mva, "x_r": 5},
            "loads": [
                {
                    "id": "load1",
                    "bus": "poi",
                    "profile": {"scenario": "unused"},
                    "transformer": TRANSFORMER_2750,
                }
            ],
        }
    )


def test_hand_calculated_transformer_voltage_drop_and_losses() -> None:
    """Exact single-branch solution in per unit on the transformer base (2.75 MVA):
    V2 = V1 − Z·conj(S/V2), with Z = transformer + the grid equivalent in series."""
    sc_mva, s_base_mva = 100.0, 2.75
    p_kw, q_kvar = 2000.0, 500.0

    z_pct, x_r = 5.75, 7.0
    r_tx = z_pct / 100 / math.sqrt(1 + x_r**2)
    x_tx = math.sqrt((z_pct / 100) ** 2 - r_tx**2)
    z_tx = complex(r_tx, x_tx)
    r_grid = s_base_mva / sc_mva / math.sqrt(1 + 5**2)
    z_grid = complex(r_grid, r_grid * 5)

    load = complex(p_kw, q_kvar) / 1000 / s_base_mva
    v2 = complex(1, 0)
    for _ in range(100):
        v2 = 1 - (z_tx + z_grid) * (load / v2).conjugate()
    current = abs((load / v2).conjugate())
    expected_loss_kw = current**2 * z_tx.real * s_base_mva * 1000
    expected_q_loss_kvar = current**2 * z_tx.imag * s_base_mva * 1000

    topology = build_topology(single_transformer_site(sc_mva))
    result = PandapowerSolver(topology).solve({load_injection("load1"): Injection(p_kw, q_kvar)})

    assert result.buses[lv_bus("load1")].vm_pu == pytest.approx(abs(v2), rel=1e-6)
    transformer = result.transformers[transformer_name("load1")]
    assert transformer.p_loss_kw == pytest.approx(expected_loss_kw, rel=1e-4)
    assert transformer.q_loss_kvar == pytest.approx(expected_q_loss_kvar, rel=1e-4)
    # Sanity against the textbook estimate ΔV ≈ (R·P + X·Q) + (X·P − R·Q)²/2 (pu, assumes
    # |V2| ≈ 1, so it reads ~3 % low at this 2.8 % drop).
    drop = (z_tx + z_grid) * load.conjugate()
    assert 1 - abs(v2) == pytest.approx(drop.real + drop.imag**2 / 2, rel=0.05)
    # The POI imports the load plus the transformer losses.
    assert result.poi.p_kw == pytest.approx(-(p_kw + expected_loss_kw), rel=1e-5)
    # Transformer convention: flow toward the grid is positive, so a load draws negative P.
    assert transformer.p_lv_kw == pytest.approx(-p_kw, rel=1e-6)
    assert transformer.p_lv_kw - transformer.p_hv_kw == pytest.approx(transformer.p_loss_kw)


def full_output_injections(config: SiteConfig) -> dict[str, Injection]:
    injections: dict[str, Injection] = {}
    for bess in config.bess:
        injections[bess_injection(bess.id)] = Injection(1500, 300)
        injections[f"bess_aux:{bess.id}"] = Injection(bess.battery.aux_load_kw, 0)
    for pv in config.pv:
        injections[pv_injection(pv.id)] = Injection(pv.inverter.p_max_kw * 0.8, -200)
    for load in config.loads:
        injections[load_injection(load.id)] = Injection(2500, 800)
    return injections


@pytest.mark.parametrize("name", ["small_1bess_1pv", "reference_2bess_1pv", "three_bess_two_pv"])
def test_power_balance(name: str) -> None:
    """POI P = ΣPV + ΣBESS − ΣLoad − Σaux − site losses (transformers + collector feeders)."""
    config = default_site(name)
    injections = full_output_injections(config)
    result = PandapowerSolver(build_topology(config)).solve(injections)

    generation = sum(
        value.p_kw for key, value in injections.items() if key.startswith(("bess:", "pv:"))
    )
    consumption = sum(
        value.p_kw for key, value in injections.items() if key.startswith(("load:", "bess_aux:"))
    )
    assert result.poi.p_kw == pytest.approx(
        generation - consumption - result.site_p_loss_kw, abs=0.05
    )
    assert result.site_p_loss_kw > 0


@pytest.mark.parametrize("units", [1, 2, 10])
def test_scaling_converges(units: int) -> None:
    config = make_site_config(n_bess=units, n_pv=units)
    solver = PandapowerSolver(build_topology(config))
    result = solver.solve(full_output_injections(config))
    assert len(result.transformers) == 2 * units
    assert all(0.9 < bus.vm_pu < 1.1 for bus in result.buses.values())


def test_non_convergence_raises_and_solver_recovers() -> None:
    config = make_site_config()
    solver = PandapowerSolver(build_topology(config))
    with pytest.raises(NonConvergenceError):
        solver.solve({load_injection("load1"): Injection(5_000_000, 0)})  # 5 GW on 100 MVA
    result = solver.solve(full_output_injections(config))
    assert 0.9 < result.buses["poi"].vm_pu < 1.1
