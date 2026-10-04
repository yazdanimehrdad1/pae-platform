"""Which buses and injections are energised: connected to the grid source through closed
breakers. Pure (no solver), so the step can zero de-energised assets before solving and the
solver can tell a dead bus (0 V) from a numerical failure.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from powerflow.network.topology import BreakerElement, Topology


@dataclass(frozen=True)
class Energization:
    buses: frozenset[str]
    injections: frozenset[str]

    def bus_live(self, bus: str) -> bool:
        return bus in self.buses

    def injection_live(self, injection: str) -> bool:
        return injection in self.injections


def out_of_service(
    topology: Topology, open_breakers: Iterable[str]
) -> dict[BreakerElement, set[str]]:
    """The elements the open breakers take out of service, by element kind."""
    opened = set(open_breakers)
    elements: dict[BreakerElement, set[str]] = defaultdict(set)
    for breaker in topology.breakers:
        if breaker.name in opened:
            elements[breaker.element_kind].add(breaker.element)
    return elements


def energize(topology: Topology, open_breakers: Iterable[str]) -> Energization:
    """Breadth-first search from the slack bus over every in-service branch."""
    dead = out_of_service(topology, open_breakers)
    neighbours: dict[str, set[str]] = defaultdict(set)

    def connect(bus: str, other: str) -> None:
        neighbours[bus].add(other)
        neighbours[other].add(bus)

    for impedance in topology.impedances:
        if impedance.name not in dead[BreakerElement.IMPEDANCE]:
            connect(impedance.from_bus, impedance.to_bus)
    for line in topology.lines:
        if line.name not in dead[BreakerElement.LINE]:
            connect(line.from_bus, line.to_bus)
    for switch in topology.switches:
        connect(switch.bus, switch.other_bus)
    for transformer in topology.transformers:
        if transformer.name not in dead[BreakerElement.TRANSFORMER]:
            connect(transformer.hv_bus, transformer.lv_bus)

    live = {topology.slack.bus}
    frontier = [topology.slack.bus]
    while frontier:
        bus = frontier.pop()
        for other in neighbours[bus] - live:
            live.add(other)
            frontier.append(other)
    injections = {
        injection.name
        for injection in topology.injections
        if injection.bus in live and injection.name not in dead[BreakerElement.INJECTION]
    }
    return Energization(buses=frozenset(live), injections=frozenset(injections))
