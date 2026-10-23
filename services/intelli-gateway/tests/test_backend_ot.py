"""The backend-ot client and connector against a fake backend-ot (no network)."""

from datetime import timedelta

import httpx
import pytest
from backend_ot_fake import FakeBackendOt
from fakes import FIXED_NOW, as_dict, fixed_clock, make_ctx, make_settings, rows

from intelli_gateway.fake_data.knowledge_store import InMemoryKnowledgeStore
from intelli_gateway.services.backend_ot.client import BackendOtClient
from intelli_gateway.services.backend_ot.site_data import (
    BackendOtSiteDataConnector,
    parse_capacity_kw,
)
from intelli_gateway.tools.catalog import build_local_tools
from intelli_gateway.tools.common import SiteToolLimits
from intelli_gateway.tools.local_provider import LocalToolProvider
from intelli_gateway.utils.exceptions import BackendOtError


@pytest.fixture
def backend() -> FakeBackendOt:
    return FakeBackendOt()


@pytest.fixture
def connector(backend: FakeBackendOt) -> BackendOtSiteDataConnector:
    client = BackendOtClient(
        "http://backend-ot.test",
        timeout_s=1,
        attempts=3,
        transport=backend.transport(),
        max_wait_s=0,
    )
    return BackendOtSiteDataConnector(client, stale_after_s=600, clock=fixed_clock)


class TestSitesAndCatalog:
    async def test_sites(self, connector: BackendOtSiteDataConnector) -> None:
        (site,) = await connector.list_sites()
        assert (site.site_id, site.name, site.capacity_kw) == (7, "Test Solar", 5000)
        assert (site.latitude, site.longitude, site.timezone) == (48.1, 11.5, "Europe/Berlin")
        assert await connector.get_site(8) is None

    async def test_points_are_qualified_with_the_device_name(
        self, connector: BackendOtSiteDataConnector
    ) -> None:
        names = [point.name for point in await connector.list_points(7)]
        assert names == [
            "INV1.active_power",
            "INV1.state",
            "INV1.alarm_word",
            "INV1.spare",
            "INV2.active_power",
        ]

    async def test_labels_and_classes(self, connector: BackendOtSiteDataConnector) -> None:
        points = {point.name: point for point in await connector.list_points(7)}
        assert points["INV1.state"].enum_labels == {3: "RUNNING", 4: "DERATED"}
        assert points["INV1.alarm_word"].bit_labels == {0: "GROUND_FAULT", 4: "OVER_TEMP"}
        assert points["INV1.alarm_word"].point_class == "ALARM"
        assert points["INV1.alarm_word"].severity == "HIGH"
        assert points["INV1.active_power"].equipment == "inverter"

    async def test_catalog_is_cached(
        self, connector: BackendOtSiteDataConnector, backend: FakeBackendOt
    ) -> None:
        await connector.list_points(7)
        await connector.list_devices(7)
        await connector.get_latest_many(7, ["INV1.state"])
        assert backend.calls["/api/devices/site/7/devices"] == 1

    async def test_topology(
        self, connector: BackendOtSiteDataConnector, backend: FakeBackendOt
    ) -> None:
        topology = await connector.get_topology(7)
        assert [node.device_id for node in topology.nodes] == [None, 1]
        assert [(c.from_id, c.to_id) for c in topology.connections] == [("poi", "inv1")]
        backend.sld_exists = False
        assert (await connector.get_topology(7)).nodes == ()


class TestReadings:
    async def test_latest_values(self, connector: BackendOtSiteDataConnector) -> None:
        latest = await connector.get_latest_many(
            7, ["INV1.active_power", "INV1.state", "INV1.alarm_word", "INV1.spare", "NOPE"]
        )
        power, state, alarms, spare = (latest[name] for name in list(latest)[:4])
        assert power is not None and power.value == 2100.5 and power.unit == "kW"
        assert power.age_s == 0 and not power.stale
        assert state is not None and state.value == 4 and state.label == "DERATED"
        assert alarms is not None and alarms.active_bits == ["OVER_TEMP"]
        assert spare is not None and spare.timestamp is None and spare.stale
        assert latest["NOPE"] is None

    async def test_same_point_name_on_two_devices(
        self, connector: BackendOtSiteDataConnector, backend: FakeBackendOt
    ) -> None:
        latest = await connector.get_latest_many(7, ["INV1.active_power", "INV2.active_power"])
        inv1, inv2 = latest["INV1.active_power"], latest["INV2.active_power"]
        assert inv1 is not None and inv1.value == 2100.5
        assert inv2 is not None and inv2.stale and inv2.age_s == 3 * 3600
        # One request per device, each asking only for its own point ids.
        asked = sorted(
            r.url.params["point_ids"] for r in backend.requests if r.url.path.endswith("/latest")
        )
        assert asked == ["11", "21"]

    async def test_history_is_sorted_and_skips_gaps(
        self, connector: BackendOtSiteDataConnector, backend: FakeBackendOt
    ) -> None:
        samples = await connector.get_history(
            7, "INV1.active_power", FIXED_NOW - timedelta(hours=1), FIXED_NOW
        )
        assert samples is not None
        assert [sample.value for sample in samples] == [1900.0, 2100.0]
        request = next(r for r in backend.requests if "timeseries" in r.url.path)
        assert request.url.params["max_points"] == "2000"
        assert request.url.params["translate"] == "true"

    async def test_state_changes(self, connector: BackendOtSiteDataConnector) -> None:
        changes = await connector.get_state_changes(
            7, "INV1.state", FIXED_NOW - timedelta(hours=4), FIXED_NOW
        )
        assert changes is not None
        assert [(c.value, c.label) for c in changes] == [(3, "RUNNING"), (4, "DERATED")]

    async def test_unknown_point(self, connector: BackendOtSiteDataConnector) -> None:
        start = FIXED_NOW - timedelta(hours=1)
        assert await connector.get_history(7, "NOPE", start, FIXED_NOW) is None
        assert await connector.get_state_changes(7, "NOPE", start, FIXED_NOW) is None


class TestAlarmsAndComms:
    async def test_active_alarms(self, connector: BackendOtSiteDataConnector) -> None:
        active = await connector.get_active_alarms(7)
        assert [(e.alarm_name, e.severity, e.device_id) for e in active.events] == [
            ("INV1 over-temperature", "warning", 1)
        ]
        (point,) = active.point_alarms
        assert point.point_name == "INV1.alarm_word"
        assert point.active_bits == ["OVER_TEMP"]

    async def test_alarm_history_is_named_and_sorted(
        self, connector: BackendOtSiteDataConnector, backend: FakeBackendOt
    ) -> None:
        events = await connector.get_alarm_events(
            7, FIXED_NOW - timedelta(days=2), FIXED_NOW, device_id=1
        )
        assert [e.cleared_at is None for e in events] == [False, True]
        assert all(e.alarm_name == "INV1 over-temperature" for e in events)
        request = next(r for r in backend.requests if r.url.path.endswith("/events"))
        assert request.url.params["device_id"] == "1"

    async def test_device_comms(self, connector: BackendOtSiteDataConnector) -> None:
        comms = {c.device_id: c for c in await connector.get_device_comms(7)}
        assert not comms[1].stale and comms[1].last_reading_at == FIXED_NOW
        assert comms[2].stale


class TestClientErrors:
    async def test_server_errors_are_retried(
        self, connector: BackendOtSiteDataConnector, backend: FakeBackendOt
    ) -> None:
        def flaky(request: httpx.Request) -> httpx.Response | None:
            return httpx.Response(503) if backend.calls[request.url.path] < 3 else None

        backend.override = flaky
        assert len(await connector.list_sites()) == 1
        assert backend.calls["/api/sites"] == 3

    async def test_gives_up_after_the_last_attempt(
        self, connector: BackendOtSiteDataConnector, backend: FakeBackendOt
    ) -> None:
        def down(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        backend.override = down
        with pytest.raises(BackendOtError, match="unreachable"):
            await connector.list_sites()
        assert backend.calls["/api/sites"] == 3

    async def test_client_errors_are_not_retried(
        self, connector: BackendOtSiteDataConnector, backend: FakeBackendOt
    ) -> None:
        backend.override = lambda request: httpx.Response(400)
        with pytest.raises(BackendOtError, match="400"):
            await connector.list_sites()
        assert backend.calls["/api/sites"] == 1

    async def test_unexpected_fields_fail_loudly(
        self, connector: BackendOtSiteDataConnector, backend: FakeBackendOt
    ) -> None:
        from backend_ot_fake import SITE

        backend.override = lambda request: httpx.Response(200, json=[{**SITE, "new_field": 1}])
        with pytest.raises(BackendOtError, match="contract drift"):
            await connector.list_sites()


class TestToolsOverBackendOt:
    async def test_tools_use_qualified_names(self, connector: BackendOtSiteDataConnector) -> None:
        limits = SiteToolLimits(
            max_rows=50, history_samples=12, history_max_days=31, max_text_chars=20_000
        )
        provider = LocalToolProvider(
            build_local_tools(connector, InMemoryKnowledgeStore([]), limits), 20_000
        )
        result = await provider.call_tool(
            "get_point_values", {"point_names": ["INV1.state"]}, make_ctx(site_id=7)
        )
        assert rows(result.content, "values")[0]["label"] == "DERATED"

    async def test_backend_down_is_an_error_result(
        self, connector: BackendOtSiteDataConnector, backend: FakeBackendOt
    ) -> None:
        def down(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        backend.override = down
        limits = SiteToolLimits(
            max_rows=50, history_samples=12, history_max_days=31, max_text_chars=20_000
        )
        provider = LocalToolProvider(
            build_local_tools(connector, InMemoryKnowledgeStore([]), limits), 20_000
        )
        result = await provider.call_tool("get_active_alarms", {}, make_ctx(site_id=7))
        assert result.is_error
        assert "backend-ot unreachable" in str(as_dict(result.content)["error"])


async def test_api_returns_503_when_backend_ot_is_down(backend: FakeBackendOt) -> None:
    from fakes import ScriptedLLMClient

    from intelli_gateway.app import create_app
    from intelli_gateway.wiring import build_services

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    backend.override = down
    client = BackendOtClient("http://backend-ot.test", 1, 1, transport=backend.transport())
    settings = make_settings(USE_FAKE_DATA="false")
    services = build_services(
        settings,
        llm=ScriptedLLMClient(),
        site_data=BackendOtSiteDataConnector(client, stale_after_s=600, clock=fixed_clock),
    )
    app = create_app(settings, services)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as http:
        response = await http.get("/api/v1/sites")
    assert response.status_code == 503
    assert "backend-ot" in response.json()["detail"]


@pytest.mark.parametrize(
    ("capacity", "kw"),
    [("5 MW", 5000), ("2500 kW", 2500), ("1,5 MW", 1500), ("750", 750), ("n/a", None)],
)
def test_parse_capacity_kw(capacity: str, kw: float | None) -> None:
    assert parse_capacity_kw(capacity) == kw
