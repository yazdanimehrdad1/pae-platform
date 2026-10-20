"""SiteConfigSource over backend-ot: a site's coordinates (with elevation) and the PV arrays of
its devices, mapped onto the forecast's SiteConfig. All backend-ot calls stay in this package."""

import logging

from intelli_gateway.schemas.backend_ot.responses import PvArrayConfigResponse, SiteResponse
from intelli_gateway.schemas.solar_forecast import ForecastLocation, PvArrayConfig, SiteConfig
from intelli_gateway.services.backend_ot.client import BackendOtClient

logger = logging.getLogger(__name__)


def to_site_config(site: SiteResponse, arrays: list[PvArrayConfigResponse]) -> SiteConfig | None:
    """None when the site can't be forecast: no coordinates, or no PV array configured."""
    if site.coordinates is None or not arrays:
        return None
    return SiteConfig(
        site_id=site.site_id,
        name=site.name,
        timezone=site.timezone,
        location=ForecastLocation(
            latitude=site.coordinates.lat,
            longitude=site.coordinates.lng,
            elevation_m=site.coordinates.elevation_m,
        ),
        arrays=tuple(
            PvArrayConfig(
                array_id=array.device_id,
                name=array.device_name,
                tilt_deg=array.tilt_deg,
                azimuth_deg=array.azimuth_deg,
                dc_capacity_kw=array.dc_capacity_kw,
                ac_capacity_kw=array.ac_capacity_kw,
                system_loss_pct=array.system_loss_pct,
                temp_coefficient_pct_per_c=array.temp_coefficient_pct_per_c,
            )
            for array in arrays
        ),
    )


class BackendOtSiteConfigSource:
    def __init__(self, client: BackendOtClient) -> None:
        self._client = client

    async def list_sites(self) -> list[SiteConfig]:
        configs: list[SiteConfig] = []
        for site in await self._client.list_sites():
            config = await self._config(site)
            if config is not None:
                configs.append(config)
        return configs

    async def get_site(self, site_id: int) -> SiteConfig | None:
        site = await self._client.get_site(site_id)
        return await self._config(site) if site is not None else None

    async def _config(self, site: SiteResponse) -> SiteConfig | None:
        arrays = await self._client.list_pv_arrays(site.site_id)
        config = to_site_config(site, arrays or [])
        if config is None:
            logger.debug(
                "site_not_forecastable",
                extra={
                    "fields": {
                        "site_id": site.site_id,
                        "has_coordinates": site.coordinates is not None,
                        "pv_arrays": len(arrays or []),
                    }
                },
            )
        return config
