"""ConfigRepository: where sites, their Modbus maps and the active site are stored.

Production uses PostgresConfigRepository (storage/postgres.py). InMemoryConfigRepository has the
same behaviour without a database, for unit tests; tests/integration runs the same contract
tests against Postgres. Name rules are enforced by the caller (SiteLibrary); a repository only
stores what it's given.
"""

from abc import ABC, abstractmethod

from powerflow.errors import NotFoundError
from powerflow.points.modbus_map import ModbusMap
from powerflow.site_config import SiteConfig


class ConfigRepository(ABC):
    @abstractmethod
    async def is_empty(self) -> bool:
        """True when no site is stored (a fresh database, ready for the defaults)."""

    @abstractmethod
    async def list_sites(self) -> list[str]: ...

    @abstractmethod
    async def get_site(self, name: str) -> SiteConfig:
        """Raises NotFoundError."""

    @abstractmethod
    async def put_site(self, name: str, config: SiteConfig) -> None:
        """Create or replace."""

    @abstractmethod
    async def delete_site(self, name: str) -> None:
        """Delete a site and its Modbus maps. Raises NotFoundError."""

    @abstractmethod
    async def get_active_site(self) -> str | None: ...

    @abstractmethod
    async def set_active_site(self, name: str) -> None:
        """Raises NotFoundError if the site doesn't exist."""

    @abstractmethod
    async def list_maps(self, site: str) -> list[str]:
        """Asset names with a map. Raises NotFoundError if the site doesn't exist."""

    @abstractmethod
    async def get_map(self, site: str, asset: str) -> ModbusMap:
        """Raises NotFoundError."""

    @abstractmethod
    async def put_map(self, site: str, asset: str, modbus_map: ModbusMap) -> None:
        """Create or replace. Raises NotFoundError if the site doesn't exist."""

    @abstractmethod
    async def delete_map(self, site: str, asset: str) -> None:
        """Raises NotFoundError."""

    @abstractmethod
    async def close(self) -> None:
        """Release connections."""


class InMemoryConfigRepository(ConfigRepository):
    def __init__(self) -> None:
        self._sites: dict[str, SiteConfig] = {}
        self._maps: dict[str, dict[str, ModbusMap]] = {}
        self._active: str | None = None

    async def is_empty(self) -> bool:
        return not self._sites

    async def list_sites(self) -> list[str]:
        return sorted(self._sites)

    async def get_site(self, name: str) -> SiteConfig:
        self._require_site(name)
        return self._sites[name]

    async def put_site(self, name: str, config: SiteConfig) -> None:
        self._sites[name] = config
        self._maps.setdefault(name, {})

    async def delete_site(self, name: str) -> None:
        self._require_site(name)
        del self._sites[name]
        self._maps.pop(name, None)
        if self._active == name:
            self._active = None

    async def get_active_site(self) -> str | None:
        return self._active

    async def set_active_site(self, name: str) -> None:
        self._require_site(name)
        self._active = name

    async def list_maps(self, site: str) -> list[str]:
        self._require_site(site)
        return sorted(self._maps[site])

    async def get_map(self, site: str, asset: str) -> ModbusMap:
        self._require_site(site)
        if asset not in self._maps[site]:
            raise NotFoundError(f"no Modbus map {asset!r} in site {site!r}")
        return self._maps[site][asset]

    async def put_map(self, site: str, asset: str, modbus_map: ModbusMap) -> None:
        self._require_site(site)
        self._maps[site][asset] = modbus_map

    async def delete_map(self, site: str, asset: str) -> None:
        await self.get_map(site, asset)
        del self._maps[site][asset]

    async def close(self) -> None:
        """Nothing to release."""

    def _require_site(self, name: str) -> None:
        if name not in self._sites:
            raise NotFoundError(f"no site {name!r}")
