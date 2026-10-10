"""
Every site profile the service knows, and the checks that run when the app starts.

To onboard a site: add its package under site_profiles/individual_sites/, import its profile
here and add it to ALL_SITE_PROFILES. A profile belongs to at most one site (sites.profile is
unique); a site without site-specific code has no profile (NULL). The router mounts one URL per entry in SITE_ENDPOINT_ROUTES. Building
that list validates every declared endpoint, and validate_site_alarms every declared alarm, so a
misdeclared one stops the app from starting instead of failing on a request or an evaluation.
validate_site_device_health does the same for the device health checks behind SLD info boxes.
"""

import re
from typing import Literal, get_type_hints

from pydantic import BaseModel

from schemas.site_profiles import AlarmCheck, DeviceHealth, FunctionKind, TimeWindowParams
from site_profiles.declarations.alarm import SiteAlarm
from site_profiles.declarations.endpoint import SiteEndpoint
from site_profiles.declarations.health import DeviceHealthCheck
from site_profiles.declarations.profile import SiteProfile
from site_profiles.individual_sites.alpha_solar.profile import ALPHA_SOLAR_PROFILE
from utils.exceptions import SiteProfileConfigError, ValidationError

ALL_SITE_PROFILES: tuple[SiteProfile, ...] = (ALPHA_SOLAR_PROFILE,)

SITE_PROFILES_BY_KEY: dict[str, SiteProfile] = {profile.key: profile for profile in ALL_SITE_PROFILES}

_COMMON_PACKAGE = "site_profiles.common"
_INDIVIDUAL_SITES_PACKAGE = "site_profiles.individual_sites"
_NAME_AFTER_PREFIX = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class SiteEndpointRoute(BaseModel):
    """One URL to mount: an endpoint name and the contract every profile declaring it shares."""

    method: Literal["GET"]
    kind: FunctionKind
    name: str
    summary: str
    params_model: type[TimeWindowParams]
    response_model: type[BaseModel]


def get_site_profile(profile_key: str) -> SiteProfile:
    """The registered profile for a non-null sites.profile value (500 if the code is missing)."""
    profile = SITE_PROFILES_BY_KEY.get(profile_key)
    if profile is None:
        raise SiteProfileConfigError(
            f"Site profile '{profile_key}' is not registered in site_profiles/profile_registry.py"
        )
    return profile


def validate_profile_key(profile_key: str | None) -> None:
    """Reject a sites.profile value that no registered profile answers to (400)."""
    if profile_key is not None and profile_key not in SITE_PROFILES_BY_KEY:
        raise ValidationError(
            f"Unknown site profile '{profile_key}'. Registered profiles: {sorted(SITE_PROFILES_BY_KEY)}"
        )


def _check_endpoint(profile_key: str, endpoint: SiteEndpoint) -> None:
    """Name matches kind, controller lives where its kind says, and returns response_model."""
    where = f"{profile_key}: endpoint '{endpoint.name}'"
    prefix = f"{endpoint.kind}-"
    if not endpoint.name.startswith(prefix) or not _NAME_AFTER_PREFIX.match(
        endpoint.name.removeprefix(prefix)
    ):
        raise SiteProfileConfigError(
            f"{where}: name must be '{prefix}' followed by lower-case words joined by '-', "
            f"e.g. '{prefix}energy-summary'"
        )

    controller = endpoint.controller
    if endpoint.kind == "common":
        package, belongs = _COMMON_PACKAGE, "site_profiles/common/"
    else:
        package = f"{_INDIVIDUAL_SITES_PACKAGE}.{profile_key}"
        belongs = f"site_profiles/individual_sites/{profile_key}/"
    if not controller.__module__.startswith(f"{package}."):
        raise SiteProfileConfigError(
            f"{where}: a {endpoint.kind} controller belongs in {belongs}, "
            f"but {controller.__qualname__} is in {controller.__module__}"
        )

    returns = get_type_hints(controller).get("return")
    if returns is not endpoint.response_model:
        raise SiteProfileConfigError(
            f"{where}: controller {controller.__qualname__} returns {returns!r}, "
            f"but the endpoint declares response_model={endpoint.response_model.__name__}"
        )


def _route_for(endpoint: SiteEndpoint) -> SiteEndpointRoute:
    return SiteEndpointRoute(
        method=endpoint.method,
        kind=endpoint.kind,
        name=endpoint.name,
        summary=endpoint.summary,
        params_model=endpoint.params_model,
        response_model=endpoint.response_model,
    )


def build_site_endpoint_routes(profiles: tuple[SiteProfile, ...]) -> list[SiteEndpointRoute]:
    """
    Validate every declared endpoint and return one route per distinct endpoint name.

    Rules:
    - profile keys are unique;
    - a name starts with its kind ('common-', 'site-', 'device-');
    - common controllers live in site_profiles/common/; site and device controllers live in
      site_profiles/individual_sites/<profile key>/;
    - the controller's return annotation is the declared response_model;
    - names are unique within a profile;
    - a name declared by several profiles has the same method, kind, params and response.
    """
    routes: dict[str, SiteEndpointRoute] = {}
    seen_keys: set[str] = set()

    for profile in profiles:
        if profile.key in seen_keys:
            raise SiteProfileConfigError(f"Duplicate site profile key '{profile.key}'")
        seen_keys.add(profile.key)

        names_in_profile: set[str] = set()
        for endpoint in profile.endpoints:
            _check_endpoint(profile.key, endpoint)
            if endpoint.name in names_in_profile:
                raise SiteProfileConfigError(f"{profile.key}: endpoint '{endpoint.name}' is declared twice")
            names_in_profile.add(endpoint.name)

            route = _route_for(endpoint)
            existing = routes.setdefault(endpoint.name, route)
            if existing != route.model_copy(update={"summary": existing.summary}):
                raise SiteProfileConfigError(
                    f"Endpoint '{endpoint.name}' has a different method/kind/params/response in "
                    f"different profiles; endpoints that share a name must share a contract"
                )

    return list(routes.values())


def _check_alarm(profile_key: str, alarm: SiteAlarm) -> None:
    """The check lives in common/ or in this profile's package, and returns AlarmCheck."""
    where = f"{profile_key}: alarm '{alarm.key}'"
    evaluate = alarm.evaluate
    packages = [_COMMON_PACKAGE, f"{_INDIVIDUAL_SITES_PACKAGE}.{profile_key}"]
    if not any(evaluate.__module__.startswith(f"{package}.") for package in packages):
        raise SiteProfileConfigError(
            f"{where}: its check belongs in site_profiles/common/ or site_profiles/individual_sites/{profile_key}/, "
            f"but {evaluate.__qualname__} is in {evaluate.__module__}"
        )
    returns = get_type_hints(evaluate).get("return")
    if returns is not AlarmCheck:
        raise SiteProfileConfigError(f"{where}: check {evaluate.__qualname__} returns {returns!r}, not AlarmCheck")


def validate_site_alarms(profiles: tuple[SiteProfile, ...]) -> None:
    """
    Validate every declared alarm:
    - the check is in site_profiles/common/ or the profile's own package, and is annotated to
      return AlarmCheck;
    - keys and names are unique within a profile (names ignoring case, like rule names).
    """
    for profile in profiles:
        keys: set[str] = set()
        names: set[str] = set()
        for alarm in profile.alarms:
            _check_alarm(profile.key, alarm)
            if alarm.key in keys:
                raise SiteProfileConfigError(f"{profile.key}: alarm key '{alarm.key}' is declared twice")
            if alarm.name.lower() in names:
                raise SiteProfileConfigError(f"{profile.key}: alarm name '{alarm.name}' is declared twice")
            keys.add(alarm.key)
            names.add(alarm.name.lower())


def _check_health(profile_key: str, check: DeviceHealthCheck) -> None:
    """The check lives in common/ or in this profile's package, and returns DeviceHealth."""
    where = f"{profile_key}: {check.node_type} health check"
    evaluate = check.evaluate
    packages = [_COMMON_PACKAGE, f"{_INDIVIDUAL_SITES_PACKAGE}.{profile_key}"]
    if not any(evaluate.__module__.startswith(f"{package}.") for package in packages):
        raise SiteProfileConfigError(
            f"{where}: {evaluate.__qualname__} belongs in site_profiles/common/ or "
            f"site_profiles/individual_sites/{profile_key}/, but is in {evaluate.__module__}"
        )
    returns = get_type_hints(evaluate).get("return")
    if returns is not DeviceHealth:
        raise SiteProfileConfigError(f"{where}: {evaluate.__qualname__} returns {returns!r}, not DeviceHealth")


def validate_site_device_health(profiles: tuple[SiteProfile, ...]) -> None:
    """
    Validate every declared device health check:
    - the check is in site_profiles/common/ or the profile's own package, and is annotated to
      return DeviceHealth;
    - at most one check per SLD element type within a profile.
    """
    for profile in profiles:
        node_types: set[str] = set()
        for check in profile.device_health:
            _check_health(profile.key, check)
            if check.node_type in node_types:
                raise SiteProfileConfigError(f"{profile.key}: {check.node_type} health check is declared twice")
            node_types.add(check.node_type)


SITE_ENDPOINT_ROUTES: list[SiteEndpointRoute] = build_site_endpoint_routes(ALL_SITE_PROFILES)
validate_site_alarms(ALL_SITE_PROFILES)
validate_site_device_health(ALL_SITE_PROFILES)
