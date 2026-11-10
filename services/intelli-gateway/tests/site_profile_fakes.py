"""A tiny fictional site for the site profile tests. Each call builds it as "backend-ot" has it at
that moment, so a test can add a device, rename one or change a point between syncs.

Site 50, "Mesa Test": meter M1 (device 1) with Power (kW), Status (enum) and Fault (an ALARM
code that is non-zero), and optionally meter M2 (device 2) with its own Fault and an active alarm
event. No signal reads another point, so renaming a device is safe.
"""

from collections.abc import Mapping

from doubles.models import (
    FakeFunction,
    FakePoint,
    FakeSite,
    Signal,
    SignalShape,
    StaticAlarmEvent,
)
from doubles.site_data import FakeSiteDataConnector
from fakes import fixed_clock
from pydantic import JsonValue

from intelli_gateway.schemas.site_data import (
    AlarmSeverity,
    Device,
    PointClass,
    PointInfo,
    Site,
    SiteFunction,
    SiteFunctionParameter,
    Topology,
    TopologyConnection,
    TopologyNode,
)

SITE_ID = 50
ON_OFF = {0: "off", 1: "on"}


def _points(device: Device, unit: str, status_labels: Mapping[int, str]) -> tuple[FakePoint, ...]:
    def info(name: str, **extra: object) -> PointInfo:
        return PointInfo.model_validate(
            {
                "name": f"{device.name}.{name}",
                "device_id": device.device_id,
                "device_name": device.name,
                "equipment": device.type.lower(),
                **extra,
            }
        )

    return (
        FakePoint(
            info=info("Power", unit=unit, point_class=PointClass.ANALOG),
            signal=Signal(shape=SignalShape.CONSTANT, base=120.0),
        ),
        FakePoint(
            info=info(
                "Status",
                data_type="enum16",
                point_class=PointClass.BINARY,
                enum_labels=dict(status_labels),
            ),
            signal=Signal(shape=SignalShape.CONSTANT, base=1),
        ),
        FakePoint(
            info=info("Fault", data_type="uint16", point_class=PointClass.ALARM, severity="HIGH"),
            signal=Signal(shape=SignalShape.CONSTANT, base=3),
        ),
    )


def mesa(
    m1_name: str = "M1",
    power_unit: str = "kW",
    status_labels: Mapping[int, str] = ON_OFF,
    with_m2: bool = False,
    site_name: str = "Mesa Test",
    functions: tuple[FakeFunction, ...] = (),
) -> FakeSite:
    m1 = Device(device_id=1, name=m1_name, type="METER", vendor="Acme", model="PM-1")
    m2 = Device(device_id=2, name="M2", type="METER")
    devices = (m1, m2) if with_m2 else (m1,)
    points = _points(m1, power_unit, status_labels)
    if with_m2:
        points += _points(m2, "kW", ON_OFF)
    return FakeSite(
        site=Site(site_id=SITE_ID, name=site_name, timezone="America/Phoenix", capacity_kw=500),
        devices=devices,
        topology=Topology(
            nodes=tuple(
                TopologyNode(
                    node_id=f"d{device.device_id}",
                    type="meter",
                    name=device.name,
                    device_id=device.device_id,
                )
                for device in devices
            )
            + (TopologyNode(node_id="poi", type="poi", name="POI"),),
            connections=tuple(
                TopologyConnection(from_id=f"d{device.device_id}", to_id="poi")
                for device in devices
            ),
        ),
        points=points,
        static_events=(
            StaticAlarmEvent(
                name="M2 comms",
                severity=AlarmSeverity.HIGH,
                message="M2 not answering",
                device_id=2,
                raised_hours_ago=1,
                duration_hours=None,
            ),
            StaticAlarmEvent(
                name="Grid event",
                severity=AlarmSeverity.MEDIUM,
                message="site-level event",
                device_id=None,
                raised_hours_ago=1,
                duration_hours=None,
            ),
        )
        if with_m2
        else (),
        functions=functions,
    )


def backend(site: FakeSite) -> FakeSiteDataConnector:
    """backend-ot as it is now: serving this one site."""
    return FakeSiteDataConnector((site,), clock=fixed_clock)


# Site functions as backend-ot labels them (results are fixed; nothing is computed).
RTE = FakeFunction(
    function=SiteFunction(name="site-rte", kind="site", summary="Round-trip efficiency (%)"),
    result={"site_id": SITE_ID, "round_trip_efficiency_pct": 88.5},
)
# Every 5 min from 06:00 to 12:00 (value = minutes after 06:00), with an outage from 07:55 to
# 09:00 that backend-ot marks with a valueless sample.
POI_SAMPLES: list[JsonValue] = [
    {
        "time": f"2026-06-15T{6 + minutes // 60:02d}:{minutes % 60:02d}:00+00:00",
        "value": float(minutes),
    }
    for minutes in range(0, 361, 5)
    if not 120 <= minutes < 180
]
POI_SAMPLES.append({"time": "2026-06-15T08:27:30+00:00", "value": None})
POI_POWER = FakeFunction(
    function=SiteFunction(
        name="site-poi-power", kind="site", summary="POI power series (kW)", output="series"
    ),
    result={
        "site_id": SITE_ID,
        "peak_kw": 450.0,
        "series": {
            "id": 0,
            "name": "poi_power",
            "unit": "kW",
            "timeseries": POI_SAMPLES,
        },
    },
)
METER_CHECK = FakeFunction(
    function=SiteFunction(
        name="device-meter-check",
        kind="device",
        summary="Meter data completeness (%)",
        device_types=("METER",),
        parameters=(
            SiteFunctionParameter(name="lookback_days", type="integer", default=7, minimum=1),
        ),
    ),
    result={"device_id": 1, "completeness_pct": 99.0},
)
INVERTER_CHECK = FakeFunction(
    function=SiteFunction(
        name="device-inverter-check",
        kind="device",
        summary="Inverter availability (%)",
        device_types=("INVERTER",),
    ),
    result={"availability_pct": 97.0},
)
# Declared in backend-ot for users only: never reaches the gateway.
USERS_ONLY = FakeFunction(
    function=SiteFunction(name="site-users-only", kind="site", summary="Users' trend"),
    result={},
    ai_assistant=False,
)
ALL_FUNCTIONS = (RTE, POI_POWER, METER_CHECK, INVERTER_CHECK, USERS_ONLY)
