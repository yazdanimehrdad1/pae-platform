"""The PowerFlowSolver interface and its solver-neutral inputs/results.

A solver is built once per topology, then solved once per step with that step's injections.
Replacing pandapower means implementing this interface; nothing else changes.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from powerflow.network.topology import Topology


@dataclass(frozen=True)
class Injection:
    """P/Q in the element's own convention (see InjectionKind): kW, kvar."""

    p_kw: float
    q_kvar: float


@dataclass(frozen=True)
class BusResult:
    vn_kv: float
    vm_pu: float
    va_degree: float

    @property
    def v_kv(self) -> float:
        return self.vm_pu * self.vn_kv


@dataclass(frozen=True)
class TransformerResult:
    """Positive = toward the grid: p_lv_kw enters at the LV terminal, p_hv_kw leaves at the HV
    terminal. Losses are always ≥ 0 (P) and include no-load losses."""

    p_hv_kw: float
    q_hv_kvar: float
    i_hv_a: float
    p_lv_kw: float
    q_lv_kvar: float
    p_loss_kw: float
    q_loss_kvar: float
    loading_pct: float


@dataclass(frozen=True)
class PoiResult:
    """Power leaving the POI bus toward the utility (export-positive), and its current."""

    p_kw: float
    q_kvar: float
    i_a: float


@dataclass(frozen=True)
class NetworkResult:
    buses: dict[str, BusResult]
    transformers: dict[str, TransformerResult]
    poi: PoiResult
    site_p_loss_kw: float
    site_q_loss_kvar: float


class PowerFlowSolver(ABC):
    """Solves the balanced, positive-sequence, steady-state power flow of one topology."""

    @abstractmethod
    def solve(self, injections: dict[str, Injection]) -> NetworkResult:
        """Solve with these injections (keyed by InjectionSpec.name; missing ones are 0).
        Raises NonConvergenceError when it doesn't converge."""


# Builds a solver for a topology (a solver class whose constructor takes the topology fits).
SolverFactory = Callable[[Topology], PowerFlowSolver]
