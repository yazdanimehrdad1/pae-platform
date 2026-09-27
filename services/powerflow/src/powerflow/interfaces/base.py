"""ProtocolAdapter interface and the adapter registry.

An adapter exposes the simulator over one protocol. It only uses the AdapterContext: the engine
for control/status, the PointRegistry to read and write points, the SetpointService, and the
SiteLibrary (stored sites, Modbus maps, profile scenarios). It never imports asset models or
the solver, so adding Modbus or DNP3 doesn't touch the core.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from powerflow.core.engine import Engine
from powerflow.core.point_registry import PointRegistry
from powerflow.core.setpoints import SetpointService
from powerflow.core.site_library import SiteLibrary
from powerflow.site_config.models import InterfacesConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdapterContext:
    engine: Engine
    points: PointRegistry
    setpoints: SetpointService
    library: SiteLibrary


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
    """Known adapter implementations by name; starts the ones the site config enables."""

    def __init__(self) -> None:
        self._factories: dict[str, AdapterFactory] = {}
        self._running: list[ProtocolAdapter] = []

    def register(self, name: str, factory: AdapterFactory) -> None:
        self._factories[name] = factory

    @property
    def available(self) -> list[str]:
        return sorted(self._factories)

    @property
    def running(self) -> list[str]:
        return [adapter.name for adapter in self._running]

    @staticmethod
    def enabled_names(interfaces: InterfacesConfig) -> list[str]:
        return [name for name, section in interfaces if getattr(section, "enabled", False)]

    async def start_enabled(self, interfaces: InterfacesConfig, context: AdapterContext) -> None:
        for name in self.enabled_names(interfaces):
            factory = self._factories.get(name)
            if factory is None:
                logger.warning("interface %r is enabled but not implemented yet; skipping", name)
                continue
            adapter = factory(context)
            await adapter.start()
            self._running.append(adapter)
            logger.info("interface %r started", name)

    async def stop_all(self) -> None:
        while self._running:
            adapter = self._running.pop()
            await adapter.stop()
            logger.info("interface %r stopped", adapter.name)
