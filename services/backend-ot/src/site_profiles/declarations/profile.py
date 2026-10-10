"""
The standard shape of a site's profile: everything one site declares in code.

Each site package builds one in its own profile.py and profile_registry.py lists it:

    SiteProfile(
        key="alpha_solar",                   # stored in sites.profile
        endpoints=(SiteEndpoint(...), ...),
        alarms=(SiteAlarm(...), ...),
        device_health=(DeviceHealthCheck(...), ...),
    )
"""

from pydantic import BaseModel, ConfigDict, Field

from site_profiles.declarations.alarm import SiteAlarm
from site_profiles.declarations.endpoint import SiteEndpoint
from site_profiles.declarations.health import DeviceHealthCheck

__all__ = ["SiteProfile"]


class SiteProfile(BaseModel):
    """The endpoints, alarms and device health checks one site offers. Its key is the value stored in
    sites.profile (unique per site)."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(..., min_length=1, max_length=64, description="Stored in sites.profile, e.g. 'alpha_solar'")
    endpoints: tuple[SiteEndpoint, ...]
    alarms: tuple[SiteAlarm, ...] = Field((), description="Alarms in code; each site with this profile gets them")
    device_health: tuple[DeviceHealthCheck, ...] = Field(
        (), description="How the site judges device health for SLD info boxes, one check per element type"
    )

    def find_alarm(self, key: str) -> SiteAlarm | None:
        """The declared alarm with this key, or None if the profile no longer declares it."""
        return next((alarm for alarm in self.alarms if alarm.key == key), None)

    def find_health_check(self, node_type: str) -> DeviceHealthCheck | None:
        """The declared health check for an SLD element type, or None if the site has none."""
        return next((check for check in self.device_health if check.node_type == node_type), None)

    def find_endpoint(self, name: str) -> SiteEndpoint | None:
        """The declared endpoint with this name, or None if the site doesn't offer it."""
        return next((endpoint for endpoint in self.endpoints if endpoint.name == name), None)
