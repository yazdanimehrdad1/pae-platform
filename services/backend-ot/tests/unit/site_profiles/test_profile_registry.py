"""
Unit tests for site_profiles.profile_registry.

Guards the startup checks on declared endpoints: a name starts with its kind ('common-',
'site-', 'device-'), common controllers live in site_profiles/common/ and site/device
controllers in site_profiles/individual_sites/<profile key>/, a controller returns the declared response_model, names are unique
within a profile, and a name declared by several profiles has one contract. Also guards
the lookups used when a request or a site write arrives.

Test controllers are defined here, so their module is this test module; each case sets
__module__ to where the controller would live.
"""

from collections.abc import Awaitable, Callable

import pytest
from pydantic import BaseModel

from schemas.site_profiles import FunctionKind, SiteContext, TimeWindowParams
from site_profiles.profile_registry import (
    SITE_ENDPOINT_ROUTES,
    SITE_PROFILES_BY_KEY,
    build_site_endpoint_routes,
    get_site_profile,
    validate_profile_key,
)
from site_profiles.site_endpoint import SiteEndpoint, SiteProfile
from utils.exceptions import SiteProfileConfigError, ValidationError

COMMON_MODULE = "site_profiles.common.functions"
SITE_MODULE = "site_profiles.individual_sites.one.functions"  # profile "one"
SITE_TWO_MODULE = "site_profiles.individual_sites.two.functions"  # profile "two"


class ResultA(BaseModel):
    value: int = 0


class ResultB(BaseModel):
    other: str = ""


class OtherParams(TimeWindowParams):
    extra: int | None = None


def make_controller(
    module: str, returns: type[BaseModel]
) -> Callable[[SiteContext, TimeWindowParams], Awaitable[BaseModel]]:
    """A fresh async controller that appears to live in `module` and is annotated to return `returns`."""

    async def controller(ctx: SiteContext, params: TimeWindowParams) -> BaseModel:
        return returns()

    controller.__annotations__["return"] = returns
    controller.__module__ = module
    return controller


def make_endpoint(
    name: str,
    kind: FunctionKind = "site",
    response_model: type[BaseModel] = ResultA,
    params_model: type[TimeWindowParams] = TimeWindowParams,
    module: str | None = None,
    returns: type[BaseModel] | None = None,
) -> SiteEndpoint:
    controller_module = module or (COMMON_MODULE if kind == "common" else SITE_MODULE)
    return SiteEndpoint(
        method="GET",
        kind=kind,
        name=name,
        controller=make_controller(controller_module, returns or response_model),
        params_model=params_model,
        response_model=response_model,
        summary="test endpoint",
    )


def make_profile(key: str, *endpoints: SiteEndpoint) -> SiteProfile:
    return SiteProfile(key=key, endpoints=endpoints)


class TestRegisteredProfiles:
    def test_default_and_alpha_solar_are_registered(self):
        assert {"default", "alpha_solar"} <= set(SITE_PROFILES_BY_KEY)

    def test_default_profile_declares_only_common_endpoints(self):
        assert {endpoint.kind for endpoint in SITE_PROFILES_BY_KEY["default"].endpoints} == {"common"}

    def test_one_route_per_declared_endpoint(self):
        assert sorted((route.kind, route.name) for route in SITE_ENDPOINT_ROUTES) == [
            ("common", "common-energy-summary"),
            ("device", "device-inverter-availability"),
            ("device", "device-plant-inverter-availability"),
            ("site", "site-poi-power"),
        ]

    def test_get_site_profile_unknown_key_is_config_error(self):
        with pytest.raises(SiteProfileConfigError):
            get_site_profile("no_such_site")

    def test_validate_profile_key(self):
        validate_profile_key(None)
        validate_profile_key("alpha_solar")
        with pytest.raises(ValidationError):
            validate_profile_key("no_such_site")


class TestEndpointChecks:
    @pytest.mark.parametrize(
        ("name", "kind"),
        [
            ("common-energy", "common"),
            ("site-poi-power", "site"),
            ("device-inverter-availability", "device"),
        ],
    )
    def test_valid_endpoint_is_accepted(self, name, kind):
        routes = build_site_endpoint_routes((make_profile("one", make_endpoint(name, kind)),))
        assert [(route.name, route.kind, route.method) for route in routes] == [(name, kind, "GET")]

    @pytest.mark.parametrize(
        ("name", "kind"),
        [
            ("poi-power", "site"),  # no prefix
            ("device-poi-power", "site"),  # prefix of another kind
            ("site-energy", "common"),
            ("site-", "site"),  # nothing after the prefix
            ("site-Poi", "site"),  # not lower-case
            ("site-poi_power", "site"),  # underscore
            ("site--poi", "site"),  # empty word
        ],
    )
    def test_name_must_be_kind_prefix_plus_slug(self, name, kind):
        with pytest.raises(SiteProfileConfigError, match="name must be"):
            build_site_endpoint_routes((make_profile("one", make_endpoint(name, kind)),))

    def test_common_controller_outside_common_package_is_rejected(self):
        endpoint = make_endpoint("common-energy", "common", module=SITE_MODULE)
        with pytest.raises(SiteProfileConfigError, match="belongs in site_profiles/common/"):
            build_site_endpoint_routes((make_profile("one", endpoint),))

    @pytest.mark.parametrize("kind", ["site", "device"])
    def test_site_or_device_controller_in_common_package_is_rejected(self, kind):
        endpoint = make_endpoint(f"{kind}-calc", kind, module=COMMON_MODULE)
        with pytest.raises(SiteProfileConfigError, match="belongs in site_profiles/individual_sites/one/"):
            build_site_endpoint_routes((make_profile("one", endpoint),))

    def test_controller_of_another_site_is_rejected(self):
        endpoint = make_endpoint("site-calc", module=SITE_TWO_MODULE)
        with pytest.raises(SiteProfileConfigError, match="belongs in site_profiles/individual_sites/one/"):
            build_site_endpoint_routes((make_profile("one", endpoint),))

    def test_controller_returning_another_model_is_rejected(self):
        endpoint = make_endpoint("site-calc", response_model=ResultA, returns=ResultB)
        with pytest.raises(SiteProfileConfigError, match="response_model=ResultA"):
            build_site_endpoint_routes((make_profile("one", endpoint),))


class TestProfilesAndContracts:
    def test_endpoint_declared_by_two_profiles_gives_one_route(self):
        shared = make_endpoint("common-energy", "common")
        routes = build_site_endpoint_routes(
            (make_profile("one", shared), make_profile("two", shared, make_endpoint("site-only-two", module=SITE_TWO_MODULE)))
        )
        assert [route.name for route in routes] == ["common-energy", "site-only-two"]

    def test_same_name_different_response_across_profiles_is_rejected(self):
        with pytest.raises(SiteProfileConfigError, match="share a contract"):
            build_site_endpoint_routes(
                (
                    make_profile("one", make_endpoint("site-calc", response_model=ResultA)),
                    make_profile("two", make_endpoint("site-calc", response_model=ResultB, module=SITE_TWO_MODULE)),
                )
            )

    def test_same_name_different_params_across_profiles_is_rejected(self):
        with pytest.raises(SiteProfileConfigError, match="share a contract"):
            build_site_endpoint_routes(
                (
                    make_profile("one", make_endpoint("site-calc")),
                    make_profile("two", make_endpoint("site-calc", params_model=OtherParams, module=SITE_TWO_MODULE)),
                )
            )

    @pytest.mark.parametrize("kind", ["site", "device"])
    def test_default_profile_with_site_or_device_endpoint_is_rejected(self, kind):
        with pytest.raises(SiteProfileConfigError, match="only common endpoints"):
            build_site_endpoint_routes((make_profile("default", make_endpoint(f"{kind}-calc", kind, module="site_profiles.individual_sites.default.functions")),))

    def test_duplicate_profile_key_is_rejected(self):
        with pytest.raises(SiteProfileConfigError, match="Duplicate"):
            build_site_endpoint_routes((make_profile("one"), make_profile("one")))

    def test_endpoint_declared_twice_is_rejected(self):
        endpoint = make_endpoint("site-calc")
        with pytest.raises(SiteProfileConfigError, match="twice"):
            build_site_endpoint_routes((make_profile("one", endpoint, endpoint),))
