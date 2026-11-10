"""Site functions: backend-ot's calculations, offered to the AI only when backend-ot labels them
ai_assistant and the site admin approves them.

Invariant guarded:
- only ai_assistant functions are copied from backend-ot; a new, changed or removed one is a
  pending change like a device or point, and the AI sees only approved ones (even when a new
  site is onboarded, each function is approved one by one);
- the gate runs only approved functions, a device function only on an approved device of a type
  it applies to, with only the parameters it declares (required ones present); max_points is
  sent only for series functions;
- results reach Claude bounded: windows longer than the limit are refused (series: 6 hours);
  a series comes as the first reading of each 15-minute interval (real backend-ot rows) or, on
  request, every reading, with its gaps and coverage (a gap is never a value);
- backend-ot's refusals (4xx) surface as InvalidRequestError with backend-ot's message;
- the admin test-run returns what the tool would, and is admin-only.
"""

from datetime import timedelta

import httpx
import pytest
from backend_ot_fake import FakeBackendOt
from doubles.knowledge_store import InMemoryKnowledgeStore
from doubles.models import FakeSite
from doubles.services import build_test_services
from doubles.site_data import FakeSiteDataConnector
from doubles.site_profile_store import InMemorySiteProfileStore
from fakes import FIXED_NOW, ScriptedLLMClient, as_dict, fixed_clock, make_ctx, make_settings
from pydantic import JsonValue
from site_profile_fakes import (
    ALL_FUNCTIONS,
    METER_CHECK,
    POI_POWER,
    POI_SAMPLES,
    RTE,
    SITE_ID,
    mesa,
)

from intelli_gateway.app import create_app
from intelli_gateway.schemas.knowledge import SitePrompt, SitePromptLinks
from intelli_gateway.schemas.site_data import SiteFunction, SiteFunctionRun
from intelli_gateway.schemas.site_profile import ChangeKind, ChangeTarget
from intelli_gateway.services.backend_ot.client import BackendOtClient
from intelli_gateway.services.backend_ot.site_data import BackendOtSiteDataConnector
from intelli_gateway.site_profile.functions import (
    FunctionLimits,
    Reading,
    find_gaps,
    first_per_interval,
    parse_readings,
    run_function,
)
from intelli_gateway.site_profile.gate import ApprovedSiteDataConnector
from intelli_gateway.site_profile.service import SiteProfileService
from intelli_gateway.tools.common import SiteToolLimits
from intelli_gateway.tools.local_provider import LocalToolProvider
from intelli_gateway.tools.site_function_tools import build_site_function_tools
from intelli_gateway.utils.exceptions import InvalidRequestError, NotFoundError

ADMIN = "admin@example.com"
START = FIXED_NOW - timedelta(days=1)
SERIES_START = FIXED_NOW - timedelta(hours=6)
FUNCTION_LIMITS = FunctionLimits(max_days=31, series_max_hours=6, interval_minutes=15)
LIMITS = SiteToolLimits(max_rows=50, history_samples=4, history_max_days=31, max_text_chars=20_000)


class Platform:
    def __init__(self, site: FakeSite) -> None:
        self.store = InMemorySiteProfileStore()
        self.now(site)

    def now(self, site: FakeSite) -> None:
        self.source = FakeSiteDataConnector((site,), clock=fixed_clock)
        self.profiles = SiteProfileService(self.store, self.source, fixed_clock, cache_ttl_s=0)
        self.gate = ApprovedSiteDataConnector(self.source, self.profiles)

    async def onboard(self) -> None:
        await self.profiles.sync_site(SITE_ID)
        await self.profiles.approve(SITE_ID, ADMIN)


def run(name: str, **extra: object) -> SiteFunctionRun:
    return SiteFunctionRun.model_validate({"name": name, "start": START, "end": FIXED_NOW, **extra})


@pytest.fixture
async def onboarded() -> Platform:
    platform = Platform(mesa(functions=ALL_FUNCTIONS))
    await platform.onboard()
    return platform


class TestProfile:
    async def test_only_functions_labelled_for_the_ai_are_pending(self) -> None:
        platform = Platform(mesa(functions=ALL_FUNCTIONS))
        pending = await platform.profiles.sync_site(SITE_ID)
        functions = [c for c in pending.changes if c.target is ChangeTarget.FUNCTION]
        assert [(c.change_id, c.kind) for c in functions] == [
            ("function:device-inverter-check", ChangeKind.ADDED),
            ("function:device-meter-check", ChangeKind.ADDED),
            ("function:site-poi-power", ChangeKind.ADDED),
            ("function:site-rte", ChangeKind.ADDED),
        ]

    async def test_onboarding_without_the_functions_leaves_them_pending(self) -> None:
        platform = Platform(mesa(functions=(RTE,)))
        pending = await platform.profiles.sync_site(SITE_ID)
        chosen = [c.change_id for c in pending.changes if c.target is not ChangeTarget.FUNCTION]
        version = await platform.profiles.approve(SITE_ID, ADMIN, chosen)
        assert version.catalog.functions == ()
        assert await platform.gate.list_site_functions(SITE_ID) == []
        still = await platform.profiles.pending_changes(SITE_ID)
        assert [c.change_id for c in still.changes] == ["function:site-rte"]

    async def test_approved_functions_reach_the_ai(self, onboarded: Platform) -> None:
        names = [f.name for f in await onboarded.gate.list_site_functions(SITE_ID)]
        assert names == [
            "device-inverter-check",
            "device-meter-check",
            "site-poi-power",
            "site-rte",
        ]

    async def test_changed_and_removed_functions_wait_for_approval(
        self, onboarded: Platform
    ) -> None:
        renamed_summary = RTE.model_copy(
            update={"function": RTE.function.model_copy(update={"summary": "RTE, SoC-corrected"})}
        )
        onboarded.now(mesa(functions=(renamed_summary, POI_POWER)))
        pending = await onboarded.profiles.sync_site(SITE_ID)
        assert [(c.change_id, c.kind, c.fields) for c in pending.changes] == [
            ("function:device-inverter-check", ChangeKind.REMOVED, ()),
            ("function:device-meter-check", ChangeKind.REMOVED, ()),
            ("function:site-rte", ChangeKind.CHANGED, ("summary",)),
        ]
        # Until approved, the AI keeps the approved definitions.
        approved = {f.name: f for f in await onboarded.gate.list_site_functions(SITE_ID)}
        assert approved["site-rte"].summary == "Round-trip efficiency (%)"
        assert "device-meter-check" in approved

        await onboarded.profiles.approve(
            SITE_ID, ADMIN, ["function:site-rte", "function:device-meter-check"]
        )
        approved = {f.name: f for f in await onboarded.gate.list_site_functions(SITE_ID)}
        assert approved["site-rte"].summary == "RTE, SoC-corrected"
        assert sorted(approved) == ["device-inverter-check", "site-poi-power", "site-rte"]


class TestGate:
    async def test_runs_an_approved_function(self, onboarded: Platform) -> None:
        result = await onboarded.gate.run_site_function(SITE_ID, run("site-rte"), 500)
        assert result == RTE.result
        # Scalar functions get no max_points.
        assert onboarded.source.function_runs[-1][2] is None

    async def test_series_functions_get_max_points(self, onboarded: Platform) -> None:
        await onboarded.gate.run_site_function(SITE_ID, run("site-poi-power"), 500)
        assert onboarded.source.function_runs[-1][2] == 500

    async def test_unapproved_or_unlabelled_function_is_refused(self) -> None:
        platform = Platform(mesa(functions=ALL_FUNCTIONS))
        await platform.profiles.sync_site(SITE_ID)
        await platform.profiles.approve(SITE_ID, ADMIN, ["site", "function:site-rte"])
        for name in ("site-poi-power", "site-users-only", "site-nothing"):
            with pytest.raises(NotFoundError):
                await platform.gate.run_site_function(SITE_ID, run(name))
        assert platform.source.function_runs == []

    async def test_site_not_onboarded_has_no_functions(self) -> None:
        platform = Platform(mesa(functions=ALL_FUNCTIONS))
        assert await platform.gate.list_site_functions(SITE_ID) == []
        with pytest.raises(NotFoundError):
            await platform.gate.run_site_function(SITE_ID, run("site-rte"))

    @pytest.mark.parametrize(
        ("request_", "error"),
        [
            (run("site-rte", device_id=1), InvalidRequestError),
            (run("device-meter-check"), InvalidRequestError),
            (run("device-meter-check", device_id=9), NotFoundError),
            (run("device-inverter-check", device_id=1), InvalidRequestError),  # M1 is a METER
            (run("device-meter-check", device_id=1, parameters={"days": 3}), InvalidRequestError),
        ],
        ids=["device-on-site-fn", "no-device", "unknown-device", "wrong-type", "unknown-param"],
    )
    async def test_bad_requests_never_reach_backend_ot(
        self, onboarded: Platform, request_: SiteFunctionRun, error: type[Exception]
    ) -> None:
        with pytest.raises(error):
            await onboarded.gate.run_site_function(SITE_ID, request_)
        assert onboarded.source.function_runs == []

    async def test_device_function_with_a_declared_parameter(self, onboarded: Platform) -> None:
        request_ = run("device-meter-check", device_id=1, parameters={"lookback_days": 3})
        assert await onboarded.gate.run_site_function(SITE_ID, request_) == METER_CHECK.result
        assert onboarded.source.function_runs[-1][1] == request_

    async def test_missing_required_parameter_is_refused(self) -> None:
        required = METER_CHECK.function.parameters[0].model_copy(update={"required": True})
        function = METER_CHECK.function.model_copy(update={"parameters": (required,)})
        platform = Platform(
            mesa(functions=(METER_CHECK.model_copy(update={"function": function}),))
        )
        await platform.onboard()
        with pytest.raises(InvalidRequestError, match="needs lookback_days"):
            await platform.gate.run_site_function(SITE_ID, run("device-meter-check", device_id=1))


class TestRunFunction:
    async def test_series_default_to_the_first_reading_of_each_15_minutes(
        self, onboarded: Platform
    ) -> None:
        request_ = SiteFunctionRun(name="site-poi-power", start=SERIES_START, end=FIXED_NOW)
        result = await run_function(onboarded.gate, SITE_ID, request_, "15min", FUNCTION_LIMITS)
        assert result.for_ai["peak_kw"] == 450.0  # the function's own fields are untouched
        # Every reading is fetched: backend-ot is not asked to sample.
        assert onboarded.source.function_runs[-1][2] is None
        series = as_dict(result.for_ai["series"])
        assert series["resolution"] == "first reading every 15 min"
        rows = series["timeseries"]
        assert isinstance(rows, list)
        # 06:00-07:45 and 09:00-12:00: the outage's intervals have no row (see the gaps).
        assert len(rows) == 21
        assert rows[:2] == [
            {"time": "2026-06-15T06:00:00+00:00", "value": 0.0},
            {"time": "2026-06-15T06:15:00+00:00", "value": 15.0},
        ]
        assert rows[7:9] == [
            {"time": "2026-06-15T07:45:00+00:00", "value": 105.0},
            {"time": "2026-06-15T09:00:00+00:00", "value": 180.0},
        ]
        assert series["gaps"] == [
            {
                "start": "2026-06-15T07:55:00+00:00",
                "end": "2026-06-15T09:00:00+00:00",
                "minutes": 65.0,
            }
        ]
        assert series["coverage_percent"] == 81.9
        # The admin gets backend-ot's untouched result to check it against.
        assert result.backend_ot == POI_POWER.result

    async def test_raw_gives_every_reading(self, onboarded: Platform) -> None:
        request_ = SiteFunctionRun(name="site-poi-power", start=SERIES_START, end=FIXED_NOW)
        result = await run_function(onboarded.gate, SITE_ID, request_, "raw", FUNCTION_LIMITS)
        series = as_dict(result.for_ai["series"])
        compact = as_dict(series["timeseries"])
        offsets, values = compact["offsets_s"], compact["values"]
        assert isinstance(offsets, list) and isinstance(values, list)
        assert (series["resolution"], compact["start"], len(values)) == (
            "every reading",
            SERIES_START.isoformat(),
            61,
        )
        assert (offsets[:2], values[:2], offsets[-1], values[-1]) == (
            [0, 300],
            [0.0, 5.0],
            21600,
            360.0,
        )
        assert None not in values  # the gap marker is a gap, not a reading
        assert series["coverage_percent"] == 81.9

    async def test_series_windows_are_limited_to_6_hours(self, onboarded: Platform) -> None:
        request_ = SiteFunctionRun(
            name="site-poi-power", start=SERIES_START - timedelta(minutes=1), end=FIXED_NOW
        )
        with pytest.raises(InvalidRequestError, match="limited to 6 hours"):
            await run_function(onboarded.gate, SITE_ID, request_, "15min", FUNCTION_LIMITS)
        assert onboarded.source.function_runs == []

    async def test_scalar_results_are_unchanged_over_long_windows(
        self, onboarded: Platform
    ) -> None:
        request_ = SiteFunctionRun(
            name="site-rte", start=FIXED_NOW - timedelta(days=31), end=FIXED_NOW
        )
        result = await run_function(onboarded.gate, SITE_ID, request_, "raw", FUNCTION_LIMITS)
        assert result.for_ai == result.backend_ot == RTE.result

    @pytest.mark.parametrize(
        ("start", "end"),
        [(FIXED_NOW, FIXED_NOW), (FIXED_NOW, START), (FIXED_NOW - timedelta(days=32), FIXED_NOW)],
        ids=["empty", "backwards", "too-long"],
    )
    async def test_bad_windows_are_refused(self, onboarded: Platform, start, end) -> None:
        request_ = SiteFunctionRun(name="site-rte", start=start, end=end)
        with pytest.raises(InvalidRequestError):
            await run_function(onboarded.gate, SITE_ID, request_, "15min", FUNCTION_LIMITS)
        assert onboarded.source.function_runs == []

    async def test_unknown_function_is_not_found(self, onboarded: Platform) -> None:
        request_ = SiteFunctionRun(name="site-nope", start=SERIES_START, end=FIXED_NOW)
        with pytest.raises(NotFoundError):
            await run_function(onboarded.gate, SITE_ID, request_, "15min", FUNCTION_LIMITS)


class TestReadingsAndGaps:
    def test_samples_without_a_number_or_outside_the_window_are_skipped(self) -> None:
        samples: list[JsonValue] = [
            {"time": "2026-06-15T10:00:00Z", "value": None},
            {"time": "2026-06-15T10:00:10Z", "value": 5},
            {"time": "2026-06-15T10:00:20Z", "value": True},
            {"time": "2026-06-15T05:00:00Z", "value": 1.0},
            {"time": "not a time", "value": 1.0},
        ]
        readings = parse_readings(samples, SERIES_START, FIXED_NOW)
        assert [reading.value for reading in readings] == [5.0]

    def test_first_per_interval_keeps_backend_ots_timestamp(self) -> None:
        times = [
            "2026-06-15T10:14:59.900000Z",
            "2026-06-15T10:15:00.100000Z",
            "2026-06-15T10:16:00Z",
        ]
        readings = parse_readings(
            [{"time": time, "value": float(index)} for index, time in enumerate(times)],
            SERIES_START,
            FIXED_NOW,
        )
        assert first_per_interval(readings, timedelta(minutes=15)) == [
            {"time": times[0], "value": 0.0},
            {"time": times[1], "value": 1.0},
        ]

    def test_no_reading_is_one_gap_over_the_whole_window(self) -> None:
        assert find_gaps([], SERIES_START, FIXED_NOW) == [(SERIES_START, FIXED_NOW)]

    def test_data_starting_late_or_stopping_early_leaves_edge_gaps(self) -> None:
        late = SERIES_START + timedelta(hours=1)
        readings = [Reading(late + timedelta(seconds=20 * i), 1.0, "") for i in range(100)]
        last = readings[-1].time
        assert find_gaps(readings, SERIES_START, FIXED_NOW) == [
            (SERIES_START, late),
            (last, FIXED_NOW),
        ]

    def test_a_pause_of_up_to_3_steps_is_not_a_gap(self) -> None:
        times = [SERIES_START + timedelta(seconds=s) for s in (0, 20, 40, 100, 120, 200)]
        readings = [Reading(time, 1.0, time.isoformat()) for time in times]
        # Steps 20, 20, 60 (3 steps: fine), 20, 80 (4 steps: a gap).
        assert find_gaps(readings, SERIES_START, times[-1]) == [(times[4], times[5])]


class TestTools:
    async def test_list_shows_which_devices_a_function_applies_to(
        self, onboarded: Platform
    ) -> None:
        provider = LocalToolProvider(
            build_site_function_tools(onboarded.gate, InMemoryKnowledgeStore([]), LIMITS), 20_000
        )
        result = await provider.call_tool("list_site_functions", {}, make_ctx(site_id=SITE_ID))
        assert not result.is_error
        functions = {f["name"]: f for f in as_dict(result.content)["functions"]}  # type: ignore[index, union-attr]
        assert functions["device-meter-check"]["devices"] == [
            {"device_id": 1, "name": "M1", "type": "METER"}
        ]
        assert functions["device-inverter-check"]["devices"] == []
        assert "devices" not in functions["site-rte"]

    async def test_run_returns_the_bounded_result(self, onboarded: Platform) -> None:
        provider = LocalToolProvider(
            build_site_function_tools(onboarded.gate, InMemoryKnowledgeStore([]), LIMITS), 20_000
        )
        args = {"name": "site-rte", "start": START.isoformat(), "end": FIXED_NOW.isoformat()}
        result = await provider.call_tool("run_site_function", args, make_ctx(site_id=SITE_ID))
        assert not result.is_error
        content = as_dict(result.content)
        assert (content["function"], content["round_trip_efficiency_pct"]) == ("site-rte", 88.5)

    async def test_refusals_become_tool_errors(self, onboarded: Platform) -> None:
        provider = LocalToolProvider(
            build_site_function_tools(onboarded.gate, InMemoryKnowledgeStore([]), LIMITS), 20_000
        )
        args = {"name": "site-nope", "start": START.isoformat(), "end": FIXED_NOW.isoformat()}
        result = await provider.call_tool("run_site_function", args, make_ctx(site_id=SITE_ID))
        assert result.is_error
        assert as_dict(result.content)["hint"] == (
            "call list_site_functions for valid names and devices"
        )

        args = {**args, "name": "device-meter-check"}
        result = await provider.call_tool("run_site_function", args, make_ctx(site_id=SITE_ID))
        assert result.is_error
        assert "give its device_id" in str(as_dict(result.content)["error"])


class TestBackendOtConnector:
    @pytest.fixture
    def connector(self) -> tuple[BackendOtSiteDataConnector, FakeBackendOt]:
        fake = FakeBackendOt()
        client = BackendOtClient("http://backend-ot", 5, 1, transport=fake.transport())
        return BackendOtSiteDataConnector(client, stale_after_s=600, clock=fixed_clock), fake

    async def test_lists_only_functions_labelled_for_the_ai(
        self, connector: tuple[BackendOtSiteDataConnector, FakeBackendOt]
    ) -> None:
        site_data, _ = connector
        functions = await site_data.list_site_functions(7)
        assert [f.name for f in functions] == ["device-availability", "site-poi-power"]
        availability = functions[0]
        assert isinstance(availability, SiteFunction)
        assert availability.device_types == ("INVERTER",)
        assert [(p.name, p.type, p.default) for p in availability.parameters] == [
            ("lookback_days", "integer", 7)
        ]

    async def test_run_sends_the_window_parameters_and_capped_max_points(
        self, connector: tuple[BackendOtSiteDataConnector, FakeBackendOt]
    ) -> None:
        site_data, fake = connector
        request_ = SiteFunctionRun(
            name="site-poi-power", start=START, end=FIXED_NOW, parameters={"lookback_days": 3}
        )
        result = await site_data.run_site_function(7, request_, max_points=50_000)
        assert result["peak_kw"] == 900.0
        params = fake.requests[-1].url.params
        assert params["start_time"] == START.isoformat()
        assert params["end_time"] == FIXED_NOW.isoformat()
        assert (params["lookback_days"], params["max_points"]) == ("3", "5000")

    @pytest.mark.parametrize(
        ("name", "device_id", "message"),
        [
            ("device-availability", 1, "no state point"),
            ("site-window-check", None, "start_time must be before"),
        ],
    )
    async def test_backend_ot_refusals_carry_its_message(
        self,
        connector: tuple[BackendOtSiteDataConnector, FakeBackendOt],
        name: str,
        device_id: int | None,
        message: str,
    ) -> None:
        site_data, _ = connector
        request_ = SiteFunctionRun(name=name, start=START, end=FIXED_NOW, device_id=device_id)
        with pytest.raises(InvalidRequestError, match=message):
            await site_data.run_site_function(7, request_)

    async def test_a_name_that_is_not_a_function_never_leaves(
        self, connector: tuple[BackendOtSiteDataConnector, FakeBackendOt]
    ) -> None:
        site_data, fake = connector
        request_ = SiteFunctionRun(name="../sites/7", start=START, end=FIXED_NOW)
        with pytest.raises(InvalidRequestError):
            await site_data.run_site_function(7, request_)
        assert fake.requests == []


class TestTestRunApi:
    @pytest.fixture
    async def app_client(self) -> httpx.AsyncClient:
        settings = make_settings(ANTHROPIC_API_KEY="test-key", TOOL_HISTORY_SAMPLES="4")
        source = FakeSiteDataConnector((mesa(functions=ALL_FUNCTIONS),), clock=fixed_clock)
        services = build_test_services(
            settings,
            llm=ScriptedLLMClient(),
            site_data=source,
            site_profile_store=InMemorySiteProfileStore(),
        )
        await services.site_profiles.sync_site(SITE_ID)
        await services.site_profiles.approve(SITE_ID, ADMIN)
        await services.auth.create_user(ADMIN, "Root", "admin", "correct horse battery")
        await services.auth.create_user(
            "ana@example.com", "Ana", "engineer", "correct horse battery"
        )
        transport = httpx.ASGITransport(app=create_app(settings, services))
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    async def login(self, client: httpx.AsyncClient, email: str) -> None:
        response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "correct horse battery"}
        )
        assert response.status_code == 200, response.text

    async def test_admin_sees_what_the_ai_would_get(self, app_client: httpx.AsyncClient) -> None:
        async with app_client as client:
            await self.login(client, ADMIN)
            response = await client.post(
                f"/api/v1/sites/{SITE_ID}/functions/site-poi-power/test-run",
                json={"start": SERIES_START.isoformat(), "end": FIXED_NOW.isoformat()},
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["function"] == "site-poi-power"
        series = body["result"]["series"]
        assert (series["resolution"], len(series["timeseries"])) == (
            "first reading every 15 min",
            21,
        )
        # backend-ot's untouched result comes along, for the admin to check against.
        assert body["backend_ot_result"]["series"]["timeseries"] == POI_SAMPLES

    async def test_admin_can_ask_for_every_reading(self, app_client: httpx.AsyncClient) -> None:
        window = {"start": SERIES_START.isoformat(), "end": FIXED_NOW.isoformat()}
        async with app_client as client:
            await self.login(client, ADMIN)
            raw = await client.post(
                f"/api/v1/sites/{SITE_ID}/functions/site-poi-power/test-run",
                json={**window, "resolution": "raw"},
            )
            too_long = await client.post(
                f"/api/v1/sites/{SITE_ID}/functions/site-poi-power/test-run",
                json={**window, "start": START.isoformat()},
            )
        assert raw.status_code == 200, raw.text
        assert len(raw.json()["result"]["series"]["timeseries"]["values"]) == 61
        assert too_long.status_code == 422

    async def test_unknown_function_is_404_bad_request_422(
        self, app_client: httpx.AsyncClient
    ) -> None:
        window = {"start": START.isoformat(), "end": FIXED_NOW.isoformat()}
        async with app_client as client:
            await self.login(client, ADMIN)
            unknown = await client.post(
                f"/api/v1/sites/{SITE_ID}/functions/site-nope/test-run", json=window
            )
            no_device = await client.post(
                f"/api/v1/sites/{SITE_ID}/functions/device-meter-check/test-run", json=window
            )
        assert unknown.status_code == 404
        assert no_device.status_code == 422

    async def test_engineers_may_not_test_run(self, app_client: httpx.AsyncClient) -> None:
        async with app_client as client:
            await self.login(client, "ana@example.com")
            response = await client.post(
                f"/api/v1/sites/{SITE_ID}/functions/site-rte/test-run",
                json={"start": START.isoformat(), "end": FIXED_NOW.isoformat()},
            )
        assert response.status_code == 403


class TestRelatedPrompts:
    async def test_a_linked_function_names_its_prompt(self, onboarded: Platform) -> None:
        knowledge = InMemoryKnowledgeStore([])
        knowledge.site_prompts.append(
            SitePrompt(
                site_id=SITE_ID,
                name="Storage",
                text="The BESS shaves the evening peak.",
                position=1,
                links=SitePromptLinks(functions=("site-rte",)),
                updated_at=FIXED_NOW,
            )
        )
        provider = LocalToolProvider(
            build_site_function_tools(onboarded.gate, knowledge, LIMITS), 20_000
        )
        listed = await provider.call_tool("list_site_functions", {}, make_ctx(site_id=SITE_ID))
        functions = {f["name"]: f for f in as_dict(listed.content)["functions"]}  # type: ignore[index, union-attr]
        assert functions["site-rte"]["related_prompts"] == ["Prompt 1: Storage"]
        assert "related_prompts" not in functions["device-meter-check"]
        args = {"name": "site-rte", "start": START.isoformat(), "end": FIXED_NOW.isoformat()}
        ran = await provider.call_tool("run_site_function", args, make_ctx(site_id=SITE_ID))
        assert as_dict(ran.content)["related_prompts"] == ["Prompt 1: Storage"]
