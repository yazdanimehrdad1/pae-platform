"""ProtocolAdapter interface and the adapter registry.

An adapter exposes the simulator over one protocol. It only uses the AdapterContext: the engine
for control/status (and injected conditions), the PointRegistry to read and write points, the
SetpointService, the SiteLibrary (stored sites, profile scenarios), the EventScenarioLibrary and
the PAE point standard. It never
imports asset models or the solver, so adding Modbus or DNP3 doesn't touch the core.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from powerflow.core.engine import Engine
from powerflow.core.event_scenario_library import EventScenarioLibrary
from powerflow.core.point_registry import PointRegistry
from powerflow.core.setpoints import SetpointService
from powerflow.core.site_library import SiteLibrary
from powerflow.point_standard import PointStandard
from powerflow.site_config.models import InterfacesConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdapterContext:
    engine: Engine
    points: PointRegistry
    setpoints: SetpointService
    library: SiteLibrary
    point_standard: PointStandard
    scenarios: EventScenarioLibrary


class ProtocolAdapter(ABC):
    name: str

    @abstractmethod
    async def start(self) -> None:
        """Start serving (open sockets, start tasks). Must return promptly."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop serving and release resources."""


AdapterFactory = Callable[[AdapterContext], ProtocolAdapter]


class AdapterRegistry:
    """Known adapter implementations by name; runs the ones the active site config enables.

    `reconcile` is the one way adapters are (re)started: at startup and after every change of the
    engine's config (activate, saving the active site). One adapter failing to start (e.g. its
    port is taken) doesn't stop the others; the failure is logged and reported in `failed`.
    """

    def __init__(self) -> None:
        self._factories: dict[str, AdapterFactory] = {}
        self._running: list[ProtocolAdapter] = []
        self.failed: dict[str, str] = {}

    def register(self, name: str, factory: AdapterFactory) -> None:
        self._factories[name] = factory

    @property
    def running(self) -> list[str]:
        return [adapter.name for adapter in self._running]

    @staticmethod
    def enabled_names(interfaces: InterfacesConfig) -> list[str]:
        return [name for name, section in interfaces if getattr(section, "enabled", False)]

    async def reconcile(self, interfaces: InterfacesConfig, context: AdapterContext) -> None:
        """Stop every running adapter, then start the ones `interfaces` enables."""
        await self.stop_all()
        self.failed = {}
        for name in self.enabled_names(interfaces):
            factory = self._factories.get(name)
            if factory is None:
                logger.warning("interface %r is enabled but not implemented yet; skipping", name)
                continue
            adapter = factory(context)
            try:
                await adapter.start()
            except OSError as error:  # e.g. the port is already in use
                logger.error("interface %r failed to start: %s", name, error)
                self.failed[name] = str(error)
                continue
            self._running.append(adapter)
            logger.info("interface %r started", name)

    async def stop_all(self) -> None:
        while self._running:
            adapter = self._running.pop()
            await adapter.stop()
            logger.info("interface %r stopped", adapter.name)
