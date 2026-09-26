"""
Every site profile the service knows, and the checks that run when the app starts.

To onboard a site: add its package under site_profiles/, import its profile here and add
it to ALL_SITE_PROFILES. The router mounts one URL per entry in SITE_ENDPOINT_ROUTES, and
building that list validates every declared endpoint, so a misdeclared endpoint stops the
app from starting instead of failing on a request.
"""

import re
from typing import Literal, get_type_hints

from pydantic import BaseModel

from schemas.site_profiles import FunctionKind, TimeWindowParams
from site_profiles.common.profile import DEFAULT_PROFILE, DEFAULT_PROFILE_KEY
from site_profiles.individual_sites.alpha_solar.profile import ALPHA_SOLAR_PROFILE
from site_profiles.site_endpoint import SiteEndpoint, SiteProfile
from utils.exceptions import SiteProfileConfigError, ValidationError

ALL_SITE_PROFILES: tuple[SiteProfile, ...] = (DEFAULT_PROFILE, ALPHA_SOLAR_PROFILE)

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
    """The registered profile for a sites.profile value (500 if the code is missing)."""
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
    - the 'default' profile declares only common endpoints;
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
            if profile.key == DEFAULT_PROFILE_KEY and endpoint.kind != "common":
                raise SiteProfileConfigError(
                    f"{profile.key}: endpoint '{endpoint.name}' is a {endpoint.kind} endpoint; the "
                    f"default profile may declare only common endpoints"
                )
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


SITE_ENDPOINT_ROUTES: list[SiteEndpointRoute] = build_site_endpoint_routes(ALL_SITE_PROFILES)
