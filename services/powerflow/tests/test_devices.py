"""The HTTP device view (/api/devices): the PAE point standard per device, with the same values
the Modbus server serves (engineering units, standard codes and labels), latest and history."""

import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import POINT_STANDARD, site_config_dict
from fastapi.testclient import TestClient

from powerflow.app import create_app
from powerflow.core.point_registry import PointRegistry
from powerflow.point_standard import build_image, build_layout, encode
from powerflow.point_standard.sources import sources_from
from powerflow.site_config import SiteConfig
from powerflow.storage import InMemoryConfigRepository

TEST_SITE = "test_site"


@pytest.fixture
def client(profiles_copy: Path) -> Iterator[TestClient]:
    raw = site_config_dict()
    raw["meters"] = [{"id": "m_bess1", "transformer": "bess1"}]
    repository = InMemoryConfigRepository.with_default_sites()

    async def fill() -> None:
        await repository.put_site(TEST_SITE, SiteConfig.model_validate(raw))
        await repository.set_active_site(TEST_SITE)

    asyncio.run(fill())
    with TestClient(create_app(profiles_copy, repository)) as test_client:
        yield test_client


def points_of(body: dict[str, Any], kind: str, asset_id: str) -> dict[str, dict[str, Any]]:
    device = next(
        item for item in body["devices"] if item["kind"] == kind and item["asset_id"] == asset_id
    )
    return {point["point"]: point for point in device["points"]}


def discharge(client: TestClient, p_kw: float) -> None:
    body = {"p_kw": p_kw, "q_kvar": 0, "mode": "pq"}
    assert client.put("/api/assets/bess/bess1/setpoint", json=body).status_code == 200


def test_no_data_before_the_first_step(client: TestClient) -> None:
    assert client.get("/api/devices").status_code == 409


def test_every_device_with_standard_values_and_labels(client: TestClient) -> None:
    discharge(client, 1200)
    snapshot = client.post("/api/sim/step").json()
    body = client.get("/api/devices").json()
    assert body["step_id"] == snapshot["step_id"]
    kinds = {(device["kind"], device["asset_id"]) for device in body["devices"]}
    assert {("site", "site"), ("bess", "bess1"), ("pv", "pv1"), ("load", "load1")} <= kinds
    assert {("poi_meter", "meter"), ("feeder_meter", "m_bess1")} <= kinds
    bess = points_of(body, "bess", "bess1")
    assert bess["W"]["value"] == pytest.approx(snapshot["bess"][0]["p_kw"] * 1000)
    assert bess["W"]["unit"] == "W" and bess["W"]["label"] == "Active Power"
    assert bess["InvSt"]["text"] == "RUNNING"
    assert bess["BrkPos"]["text"] == "CLOSED"
    assert bess["WSet"]["value"] == pytest.approx(1_200_000)
    unserved = next(point for point in bess.values() if point["served"] == "no")
    assert unserved["value"] is None and unserved["text"] is None


def test_values_are_what_modbus_serves(client: TestClient) -> None:
    """Every served value encodes to exactly the register words the Modbus server holds."""
    discharge(client, -800)
    client.post("/api/sim/step", params={"count": 3})
    body = client.get("/api/devices").json()
    context = client.app.state.context  # type: ignore[attr-defined]
    engine = context.engine
    registry: PointRegistry = context.points
    assert engine.store.latest is not None
    sources = sources_from(engine.store.latest, engine.config, registry, POINT_STANDARD.enums)
    devices = build_layout(engine.config, POINT_STANDARD)
    image = build_image(devices, sources)
    checked = 0
    for device in devices:
        readings = points_of(body, str(device.kind), device.asset_id)
        for register in device.registers:
            value = readings[register.row.point]["value"]
            if value is None:
                continue
            words = encode(value, register.row)
            assert words == [image[register.address + index] for index in range(len(words))]
            checked += 1
    assert checked > 100


def test_one_device_and_errors(client: TestClient) -> None:
    client.post("/api/sim/step")
    body = client.get("/api/devices/feeder_meter/m_bess1").json()
    assert [device["asset_id"] for device in body["devices"]] == ["m_bess1"]
    assert client.get("/api/devices/bess/nope").status_code == 404
    assert client.get("/api/devices/rocket/bess1").status_code == 422


def test_history_per_point(client: TestClient) -> None:
    discharge(client, 1000)
    client.post("/api/sim/step", params={"count": 4})
    response = client.get(
        "/api/devices/bess/bess1/history", params=[("points", "W"), ("points", "WSet")]
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [point["point"] for point in body["points"]] == ["W", "WSet"]
    assert [sample["step_id"] for sample in body["samples"]] == [1, 2, 3, 4]
    assert body["samples"][-1]["values"][0] == pytest.approx(1_000_000)
    # Setpoints aren't recorded in history: a value derived from one is null, not today's value.
    assert all(sample["values"][1] is None for sample in body["samples"])
    unknown = client.get("/api/devices/bess/bess1/history", params={"points": "Nope"})
    assert unknown.status_code == 404
    assert client.get("/api/devices/bess/bess1/history").status_code == 422


def test_point_labels_come_from_the_csvs() -> None:
    labelled = [row for rows in POINT_STANDARD.point_lists.values() for row in rows if row.label]
    assert len(labelled) == sum(len(rows) for rows in POINT_STANDARD.point_lists.values())
