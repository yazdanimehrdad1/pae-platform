"""Event scenarios: scheduling (step and sim-time triggers, missed events, skipped ticks), the
engine playing one deterministically, and the HTTP API (per-site CRUD, start/stop)."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from conftest import PROFILES, make_site_config, site_config_dict
from fastapi.testclient import TestClient

from powerflow.app import create_app
from powerflow.conditions import AssetFaultChange, BreakerChange, GridVoltageChange
from powerflow.conditions.scenario import (
    EventScenario,
    ScenarioEvent,
    StepTrigger,
    TimeTrigger,
    due,
    first_step_at,
    schedule,
    validate_scenario,
)
from powerflow.core.engine import Engine
from powerflow.core.runtime import SiteRuntime
from powerflow.errors import ConditionError, InvalidStateError
from powerflow.models.bess import BessStatus
from powerflow.network.pandapower_solver import PandapowerSolver
from powerflow.site_config import SiteConfig
from powerflow.storage import InMemoryConfigRepository

ORIGIN = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)


def open_at(step: int, breaker: str = "bess1") -> ScenarioEvent:
    return ScenarioEvent(
        at=StepTrigger(step=step), change=BreakerChange(breaker=breaker, closed=False)
    )


class TestSchedule:
    def test_step_triggers_count_from_the_start(self) -> None:
        run = schedule("s", EventScenario(events=[open_at(3), open_at(1)]), 10, ORIGIN, 1.0)
        assert [event.step for event in run.pending] == [11, 13]

    def test_time_triggers_and_missed_events(self) -> None:
        events = [
            ScenarioEvent(
                at=TimeTrigger(sim_time=ORIGIN + timedelta(seconds=20.5)),
                change=GridVoltageChange(vm_pu=0.9),
            ),
            ScenarioEvent(
                at=TimeTrigger(sim_time=ORIGIN + timedelta(seconds=5)),
                change=GridVoltageChange(vm_pu=None),
            ),
        ]
        run = schedule("s", EventScenario(events=events), 10, ORIGIN, 1.0)
        assert [event.step for event in run.pending] == [21]  # the first step at/after 20.5 s
        assert run.missed == 1 and run.total == 2

    def test_first_step_at(self) -> None:
        assert first_step_at(ORIGIN + timedelta(seconds=10), ORIGIN, 1.0) == 10
        assert first_step_at(ORIGIN + timedelta(seconds=10.2), ORIGIN, 5.0) == 3

    def test_due_takes_everything_up_to_the_step_in_order(self) -> None:
        scenario = EventScenario(events=[open_at(2, "pv1"), open_at(1), open_at(2, "load1")])
        run = schedule("s", scenario, 0, ORIGIN, 1.0)
        changes, run = due(run, 1)
        assert [change.breaker for change in changes] == ["bess1"]  # type: ignore[union-attr]
        changes, run = due(run, 5)  # skipped ticks: the whole gap, in list order
        assert [change.breaker for change in changes] == ["pv1", "load1"]  # type: ignore[union-attr]
        assert run.fired == 3 and not run.pending

    def test_validation_names_each_bad_event(self) -> None:
        scenario = EventScenario(events=[open_at(1), open_at(2, "nope"), open_at(3, "poi")])
        problems = validate_scenario(scenario, make_site_config())
        assert len(problems) == 1 and problems[0].startswith("event 2:")

    def test_an_empty_scenario_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            EventScenario(events=[])


def make_engine() -> Engine:
    config = SiteConfig.model_validate(site_config_dict())
    return Engine(SiteRuntime.build(config, PROFILES, PandapowerSolver), PandapowerSolver, PROFILES)


class TestEnginePlayer:
    def test_events_fire_before_their_step(self) -> None:
        engine = make_engine()
        asyncio.run(engine.step(5))
        scenario = EventScenario(
            events=[
                ScenarioEvent(at=StepTrigger(step=2), change=AssetFaultChange(asset_id="bess1")),
                ScenarioEvent(
                    at=StepTrigger(step=4),
                    change=AssetFaultChange(asset_id="bess1", active=False),
                ),
            ]
        )
        report = asyncio.run(engine.start_scenario("trip", scenario))
        assert report.scenario is not None and report.scenario.next_step == 7
        statuses = [asyncio.run(engine.step(1)).bess[0].status for _ in range(5)]
        assert statuses == [
            BessStatus.IDLE,
            BessStatus.FAULT,  # step 7
            BessStatus.FAULT,
            BessStatus.IDLE,  # step 9: cleared
            BessStatus.IDLE,
        ]
        finished = engine.active_conditions().scenario
        assert finished is not None and finished.finished and finished.fired == 2
        assert engine.status().scenario == "trip"

    def test_one_at_a_time_and_stop_keeps_conditions(self) -> None:
        engine = make_engine()
        asyncio.run(engine.start_scenario("a", EventScenario(events=[open_at(1), open_at(9)])))
        with pytest.raises(InvalidStateError):
            asyncio.run(engine.start_scenario("b", EventScenario(events=[open_at(1)])))
        asyncio.run(engine.step(1))
        report = asyncio.run(engine.stop_scenario())
        assert report.scenario is None
        assert not next(item for item in report.breakers if item.id == "bess1").closed

    def test_invalid_scenario_is_refused(self) -> None:
        engine = make_engine()
        with pytest.raises(ConditionError):
            asyncio.run(engine.start_scenario("x", EventScenario(events=[open_at(1, "nope")])))

    def test_clear_and_reset_stop_it(self) -> None:
        engine = make_engine()
        asyncio.run(engine.start_scenario("a", EventScenario(events=[open_at(5)])))
        assert engine.clear_conditions().scenario is None
        asyncio.run(engine.start_scenario("a", EventScenario(events=[open_at(5)])))
        asyncio.run(engine.reset())
        assert engine.active_conditions().scenario is None


TEST_SITE = "test_site"
SCENARIO_BODY: dict[str, Any] = {
    "description": "Trip BESS 1, then restore it",
    "events": [
        {
            "at": {"kind": "step", "step": 1},
            "change": {"type": "asset_fault", "asset_id": "bess1"},
            "label": "trip",
        },
        {
            "at": {"kind": "step", "step": 3},
            "change": {"type": "asset_fault", "asset_id": "bess1", "active": False},
        },
    ],
}


@pytest.fixture
def client(profiles_copy: Path) -> Iterator[TestClient]:
    repository = InMemoryConfigRepository.with_default_sites()

    async def fill() -> None:
        await repository.put_site(TEST_SITE, make_site_config())
        await repository.set_active_site(TEST_SITE)

    asyncio.run(fill())
    with TestClient(create_app(profiles_copy, repository)) as test_client:
        yield test_client


class TestApi:
    def test_conditions_round_trip(self, client: TestClient) -> None:
        response = client.post(
            "/api/sim/conditions", json={"type": "breaker", "breaker": "bess1", "closed": False}
        )
        assert response.status_code == 200, response.text
        assert not next(item for item in response.json()["breakers"] if item["id"] == "bess1")[
            "closed"
        ]
        bess = client.post("/api/sim/step").json()["bess"][0]
        assert bess["breaker_state_name"] == "OPEN"
        missing = {"type": "asset_fault", "asset_id": "nope"}
        assert client.post("/api/sim/conditions", json=missing).status_code == 404
        on_load = {"type": "asset_fault", "asset_id": "load1"}
        assert client.post("/api/sim/conditions", json=on_load).status_code == 422
        cleared = client.post("/api/sim/conditions/clear").json()
        assert all(item["closed"] for item in cleared["breakers"])

    def test_scenario_crud_and_play(self, client: TestClient) -> None:
        base = f"/api/sites/{TEST_SITE}/event-scenarios"
        assert client.put(f"{base}/trip", json=SCENARIO_BODY).status_code == 200
        listed = client.get(base).json()
        assert listed == [
            {
                "name": "trip",
                "description": "Trip BESS 1, then restore it",
                "event_count": 2,
                "valid": True,
                "problems": [],
            }
        ]
        assert client.get(f"{base}/trip").json()["events"][0]["label"] == "trip"
        started = client.post("/api/sim/event-scenario/start", json={"name": "trip"})
        assert started.status_code == 200 and started.json()["scenario"]["name"] == "trip"
        conflict = client.post("/api/sim/event-scenario/start", json={"name": "trip"})
        assert conflict.status_code == 409
        assert client.post("/api/sim/step").json()["bess"][0]["status_name"] == "FAULT"
        assert client.post("/api/sim/event-scenario/stop").json()["scenario"] is None
        assert client.delete(f"{base}/trip").status_code == 204
        assert client.get(f"{base}/trip").status_code == 404

    def test_scenarios_are_checked_against_their_site(self, client: TestClient) -> None:
        bad = {
            "events": [
                {
                    "at": {"kind": "step", "step": 1},
                    "change": {"type": "breaker", "breaker": "bess9", "closed": False},
                }
            ]
        }
        response = client.put(f"/api/sites/{TEST_SITE}/event-scenarios/bad", json=bad)
        assert response.status_code == 422 and "bess9" in response.json()["detail"]
        assert client.get("/api/sites/nope/event-scenarios").status_code == 404
        unknown = client.post("/api/sim/event-scenario/start", json={"name": "none"})
        assert unknown.status_code == 404

    def test_a_site_edit_can_make_a_scenario_stale(self, client: TestClient) -> None:
        base = f"/api/sites/{TEST_SITE}/event-scenarios"
        client.put(f"{base}/trip", json=SCENARIO_BODY)
        client.post("/api/sim/stop")
        raw = site_config_dict()
        raw["bess"][0]["id"] = "bess_renamed"
        assert client.put(f"/api/sites/{TEST_SITE}", json=raw).status_code == 200
        listed = client.get(base).json()[0]
        assert not listed["valid"] and "bess1" in listed["problems"][0]
