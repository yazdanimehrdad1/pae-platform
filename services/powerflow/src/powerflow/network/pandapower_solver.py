"""PowerFlowSolver on pandapower (Newton-Raphson). The only module that imports pandapower.

The net is built once from the Topology; each solve only rewrites the sgen/load P and Q.
BESS and PV are `sgen` (generator convention, so a charging BESS is a negative sgen).
"""

import logging
import math
import warnings

import pandapower as pp
from pandapower.auxiliary import pandapowerNet
from pandapower.powerflow import LoadflowNotConverged

from powerflow.errors import NonConvergenceError
from powerflow.network.solver import (
    BusResult,
    Injection,
    NetworkResult,
    PoiResult,
    PowerFlowSolver,
    TransformerResult,
)
from powerflow.network.topology import InjectionKind, PoiBranchKind, Topology

logger = logging.getLogger(__name__)

# System base for per-unit impedances (any value works; results are in physical units).
SYSTEM_BASE_MVA = 1.0
KW_PER_MW = 1000.0


class PandapowerSolver(PowerFlowSolver):
    def __init__(self, topology: Topology) -> None:
        self._topology = topology
        self._net: pandapowerNet = pp.create_empty_network(sn_mva=SYSTEM_BASE_MVA)
        self._bus_index: dict[str, int] = {}
        self._sgen_index: dict[str, int] = {}
        self._load_index: dict[str, int] = {}
        self._trafo_index: dict[str, int] = {}
        self._line_index: dict[str, int] = {}
        self._impedance_index: dict[str, int] = {}
        self._has_result = False
        self._build()

    def _build(self) -> None:
        net = self._net
        topology = self._topology
        for bus in topology.buses:
            self._bus_index[bus.name] = int(pp.create_bus(net, vn_kv=bus.vn_kv, name=bus.name))
        slack = topology.slack
        pp.create_ext_grid(
            net,
            self._bus_index[slack.bus],
            vm_pu=slack.vm_pu,
            va_degree=slack.va_degree,
            # Short-circuit data only matters for future fault studies: the source impedance
            # the power flow sees is the explicit impedance element below.
            s_sc_max_mva=slack.sc_mva,
            rx_max=1.0 / slack.x_r,
        )
        for impedance in topology.impedances:
            z_base_ohm = impedance.vn_kv**2 / SYSTEM_BASE_MVA
            self._impedance_index[impedance.name] = int(
                pp.create_impedance(
                    net,
                    self._bus_index[impedance.from_bus],
                    self._bus_index[impedance.to_bus],
                    rft_pu=impedance.r_ohm / z_base_ohm,
                    xft_pu=impedance.x_ohm / z_base_ohm,
                    sn_mva=SYSTEM_BASE_MVA,
                    name=impedance.name,
                )
            )
        for line in topology.lines:
            self._line_index[line.name] = int(
                pp.create_line_from_parameters(
                    net,
                    self._bus_index[line.from_bus],
                    self._bus_index[line.to_bus],
                    length_km=line.length_km,
                    r_ohm_per_km=line.r_ohm_per_km,
                    x_ohm_per_km=line.x_ohm_per_km,
                    c_nf_per_km=line.c_nf_per_km,
                    max_i_ka=line.max_i_ka,
                    name=line.name,
                )
            )
        for switch in topology.switches:
            pp.create_switch(
                net,
                self._bus_index[switch.bus],
                self._bus_index[switch.other_bus],
                et="b",
                closed=True,
                name=switch.name,
            )
        for transformer in topology.transformers:
            self._trafo_index[transformer.name] = int(
                pp.create_transformer_from_parameters(
                    net,
                    self._bus_index[transformer.hv_bus],
                    self._bus_index[transformer.lv_bus],
                    sn_mva=transformer.sn_kva / KW_PER_MW,
                    vn_hv_kv=transformer.vn_hv_kv,
                    vn_lv_kv=transformer.vn_lv_kv,
                    vkr_percent=transformer.vkr_pct,
                    vk_percent=transformer.vk_pct,
                    pfe_kw=transformer.pfe_kw,
                    i0_percent=transformer.i0_pct,
                    name=transformer.name,
                )
            )
        for injection in topology.injections:
            bus = self._bus_index[injection.bus]
            if injection.kind is InjectionKind.GENERATOR:
                self._sgen_index[injection.name] = int(
                    pp.create_sgen(net, bus, p_mw=0.0, q_mvar=0.0, name=injection.name)
                )
            else:
                self._load_index[injection.name] = int(
                    pp.create_load(net, bus, p_mw=0.0, q_mvar=0.0, name=injection.name)
                )

    def solve(self, injections: dict[str, Injection]) -> NetworkResult:
        net = self._net
        for name, index in self._sgen_index.items():
            injection = injections.get(name, Injection(0.0, 0.0))
            net.sgen.at[index, "p_mw"] = injection.p_kw / KW_PER_MW
            net.sgen.at[index, "q_mvar"] = injection.q_kvar / KW_PER_MW
        for name, index in self._load_index.items():
            injection = injections.get(name, Injection(0.0, 0.0))
            net.load.at[index, "p_mw"] = injection.p_kw / KW_PER_MW
            net.load.at[index, "q_mvar"] = injection.q_kvar / KW_PER_MW

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # pandas/numba chatter from inside pandapower
                pp.runpp(
                    net,
                    algorithm="nr",
                    init="results" if self._has_result else "auto",
                    numba=False,
                )
        except LoadflowNotConverged as error:
            self._has_result = False  # don't warm-start from a diverged state
            raise NonConvergenceError(str(error) or "power flow did not converge") from error
        self._has_result = True
        return self._results()

    def _results(self) -> NetworkResult:
        net = self._net
        buses = {
            bus.name: BusResult(
                vn_kv=bus.vn_kv,
                vm_pu=float(net.res_bus.at[self._bus_index[bus.name], "vm_pu"]),
                va_degree=float(net.res_bus.at[self._bus_index[bus.name], "va_degree"]),
            )
            for bus in self._topology.buses
        }
        transformers: dict[str, TransformerResult] = {}
        for name, index in self._trafo_index.items():
            row = net.res_trafo.loc[index]
            transformers[name] = TransformerResult(
                p_hv_kw=-float(row["p_hv_mw"]) * KW_PER_MW,
                q_hv_kvar=-float(row["q_hv_mvar"]) * KW_PER_MW,
                i_hv_a=float(row["i_hv_ka"]) * KW_PER_MW,  # kA → A, same factor
                p_lv_kw=float(row["p_lv_mw"]) * KW_PER_MW,
                q_lv_kvar=float(row["q_lv_mvar"]) * KW_PER_MW,
                p_loss_kw=float(row["pl_mw"]) * KW_PER_MW,
                q_loss_kvar=float(row["ql_mvar"]) * KW_PER_MW,
                loading_pct=float(row["loading_percent"]),
            )

        topology = self._topology
        if topology.poi_branch_kind is PoiBranchKind.LINE:
            row = net.res_line.loc[self._line_index[topology.poi_branch]]
        else:
            row = net.res_impedance.loc[self._impedance_index[topology.poi_branch]]
        poi = PoiResult(
            p_kw=float(row["p_from_mw"]) * KW_PER_MW,
            q_kvar=float(row["q_from_mvar"]) * KW_PER_MW,
            i_a=float(row["i_from_ka"]) * KW_PER_MW,
        )

        p_loss_kw = sum(result.p_loss_kw for result in transformers.values())
        q_loss_kvar = sum(result.q_loss_kvar for result in transformers.values())
        for name in topology.site_lines:
            line = net.res_line.loc[self._line_index[name]]
            p_loss_kw += float(line["pl_mw"]) * KW_PER_MW
            q_loss_kvar += float(line["ql_mvar"]) * KW_PER_MW

        if not all(math.isfinite(bus.vm_pu) for bus in buses.values()):
            raise NonConvergenceError("power flow returned non-finite voltages")
        return NetworkResult(
            buses=buses,
            transformers=transformers,
            poi=poi,
            site_p_loss_kw=p_loss_kw,
            site_q_loss_kvar=q_loss_kvar,
        )
