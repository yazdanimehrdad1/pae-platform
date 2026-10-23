"""Where the forecast gets its sites: location and PV arrays. backend-ot owns that data
(services/backend_ot/site_config.py); fake_data has fictional ones."""

from typing import Protocol

from intelli_gateway.schemas.solar_forecast import SiteConfig


class SiteConfigSource(Protocol):
    async def list_sites(self) -> list[SiteConfig]:
        """Every site that can be forecast: it has coordinates and at least one PV array."""
        ...

    async def get_site(self, site_id: int) -> SiteConfig | None:
        """None when the site doesn't exist or can't be forecast (no coordinates or arrays)."""
        ...
