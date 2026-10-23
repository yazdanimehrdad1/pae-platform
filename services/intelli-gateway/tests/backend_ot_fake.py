"""A tiny fake backend-ot HTTP API (httpx.MockTransport) for the backend-ot client tests.

Payloads follow contracts/openapi/backend-ot.openapi.json. Everything here is fictional.
"""

from collections import Counter
from collections.abc import Callable

import httpx
from fakes import FIXED_NOW

NOW = FIXED_NOW.isoformat()
EARLIER = "2026-06-15T11:59:00+00:00"
STALE = "2026-06-15T09:00:00+00:00"
CREATED = "2026-01-01T00:00:00+00:00"

SITE = {
    "site_id": 7,
    "client_id": "c1",
    "name": "Test Solar",
    "operator": "op",
    "capacity": "5 MW",
    "device_count": 2,
    "created_at": CREATED,
    "updated_at": CREATED,
    "last_update": NOW,
    "coordinates": {"lat": 48.1, "lng": 11.5},
    "timezone": "Europe/Berlin",
}


def _point(
    point_id: int, device_id: int, name: str, data_type: str, **extra: object
) -> dict[str, object]:
    return {
        "id": point_id,
        "site_id": 7,
        "device_id": device_id,
        "name": name,
        "address": point_id,
        "size": 1,
        "data_type": data_type,
        **extra,
    }


def _device(device_id: int, name: str, points: list[dict[str, object]]) -> dict[str, object]:
    return {
        "device_id": device_id,
        "site_id": 7,
        "name": name,
        "type": "INVERTER",
        "protocol": "Modbus",
        "host": "10.0.0.1",
        "port": 502,
        "server_address": device_id,
        "created_at": CREATED,
        "updated_at": CREATED,
        "vendor": "Fictional Power",
        "model": "FP-1",
        "points": {"native": points, "standardized": [], "virtual": []},
    }


# Both inverters have a point called `active_power`: names are unique only per device.
DEVICES = [
    _device(
        1,
        "INV1",
        [
            _point(11, 1, "active_power", "float32", unit="kW", **{"class": "ANALOG"}),
            _point(
                12,
                1,
                "state",
                "enum16",
                enum_detail={"3": "RUNNING", "4": "DERATED"},
                **{"class": "BINARY"},
            ),
            _point(
                13,
                1,
                "alarm_word",
                "bitfield16",
                bitfield_detail={"bit-0": "GROUND_FAULT", "4": "OVER_TEMP"},
                severity="HIGH",
                **{"class": "ALARM"},
            ),
            _point(14, 1, "spare", "uint16"),
        ],
    ),
    _device(2, "INV2", [_point(21, 2, "active_power", "float32", unit="kW")]),
]

LATEST = {
    1: {
        "11": {
            "id": 11,
            "name": "active_power",
            "data_type": "float32",
            "time": NOW,
            "value": 2100.5,
            "unit": "kW",
        },
        "12": {
            "id": 12,
            "name": "state",
            "data_type": "enum16",
            "time": NOW,
            "value": 4,
            "translated_value": "DERATED",
        },
        "13": {
            "id": 13,
            "name": "alarm_word",
            "data_type": "bitfield16",
            "time": NOW,
            "value": 16,
            "translated_value": {"GROUND_FAULT": 0, "OVER_TEMP": 1},
        },
        # Never read: backend-ot returns the point with no time and no value.
        "14": {"id": 14, "name": "spare", "data_type": "uint16", "time": None, "value": None},
    },
    2: {
        "21": {
            "id": 21,
            "name": "active_power",
            "data_type": "float32",
            "time": STALE,
            "value": 0.0,
            "unit": "kW",
        },
    },
}

TIMESERIES = {
    11: [  # out of order on purpose, with one missing value
        {"time": NOW, "value": 2100.0},
        {"time": "2026-06-15T11:50:00+00:00", "value": 1900.0},
        {"time": "2026-06-15T11:55:00+00:00", "value": None},
    ],
    12: [
        {"time": "2026-06-15T09:00:00+00:00", "value": 3, "translated_value": "RUNNING"},
        {"time": "2026-06-15T09:05:00+00:00", "value": 3, "translated_value": "RUNNING"},
        {"time": "2026-06-15T09:10:00+00:00", "value": 4, "translated_value": "DERATED"},
        {"time": "2026-06-15T09:15:00+00:00", "value": 4, "translated_value": "DERATED"},
    ],
}

DEFINITION = {
    "id": 5,
    "site_id": 7,
    "source": "USER",
    "name": "INV1 over-temperature",
    "kind": "condition",
    "severity": "warning",
    "message": "INV1 hot",
    "enabled": True,
    "notify_mobile": False,
    "notify_email": False,
    "created_at": CREATED,
    "updated_at": CREATED,
}
ACTIVE_EVENT = {
    "id": 100,
    "definition_id": 5,
    "site_id": 7,
    "severity": "warning",
    "raised_at": EARLIER,
    "message": "INV1 hot",
    "device_id": 1,
}
CLEARED_EVENT = {
    "id": 99,
    "definition_id": 5,
    "site_id": 7,
    "severity": "warning",
    "raised_at": "2026-06-14T10:00:00+00:00",
    "cleared_at": "2026-06-14T18:00:00+00:00",
    "message": "INV1 hot",
    "device_id": 1,
}

SNAPSHOT = {
    "site_id": 7,
    "now": NOW,
    "definitions": [DEFINITION],
    "events": [ACTIVE_EVENT, CLEARED_EVENT],
    "log": [],
}
HEALTH = {
    "site_id": 7,
    "generated_at": NOW,
    "devices": [
        {
            "device_id": 1,
            "device_name": "INV1",
            "active_alarms": [
                {
                    "device_point_id": 13,
                    "device_point_name": "alarm_word",
                    "value": 16,
                    "timestamp": NOW,
                    "active_bits": ["OVER_TEMP"],
                    "severity": "HIGH",
                }
            ],
        }
    ],
}
SLD = {
    "site_id": 7,
    "revision": 1,
    "created_at": CREATED,
    "updated_at": CREATED,
    "sld": {
        "schema_version": 1,
        "nodes": [
            {"id": "poi", "type": "poi", "name": "POI", "col": 0, "row": 0},
            {
                "id": "inv1",
                "type": "inverter",
                "name": "INV1",
                "col": 1,
                "row": 1,
                "device": {"device_id": 1, "points": {}},
            },
        ],
        "connections": [{"from_id": "poi", "to_id": "inv1"}],
    },
}


class FakeBackendOt:
    """Routes requests to the payloads above; records what was called."""

    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()
        self.requests: list[httpx.Request] = []
        self.override: Callable[[httpx.Request], httpx.Response | None] | None = None
        self.sld_exists = True

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        self.calls[path] += 1
        if self.override is not None:
            overridden = self.override(request)
            if overridden is not None:
                return overridden
        params = request.url.params
        if path == "/api/sites":
            return httpx.Response(200, json=[SITE])
        if path == "/api/sites/7":
            return httpx.Response(200, json=SITE)
        if path.startswith("/api/sites/") and path.count("/") == 3:
            return httpx.Response(404, json={"detail": "site not found"})
        if path == "/api/devices/site/7/devices":
            return httpx.Response(200, json=DEVICES)
        if path == "/api/sites/7/sld":
            return httpx.Response(200, json=SLD) if self.sld_exists else httpx.Response(404)
        if path.startswith("/api/device-point-readings/site/7/device/"):
            device_id = int(path.split("/")[-2])
            wanted = params.get("point_ids")
            readings = LATEST[device_id]
            if wanted:
                readings = {k: v for k, v in readings.items() if k in wanted.split(",")}
            meta = {"site_id": 7, "device_id": device_id, "total_count": len(readings)}
            return httpx.Response(200, json={"meta": meta, "readings": readings})
        if path.startswith("/api/device-point-readings/timeseries/site/7/device/"):
            device_id = int(path.split("/")[-1])
            point_id = int(params["point_ids"])
            series = {
                "id": point_id,
                "name": "p",
                "data_type": "float32",
                "count": len(TIMESERIES.get(point_id, [])),
                "timeseries": TIMESERIES.get(point_id, []),
            }
            meta = {"site_id": 7, "device_id": device_id, "total_count": 1}
            return httpx.Response(200, json={"meta": meta, "readings": {str(point_id): series}})
        if path == "/api/alarms/site/7/snapshot":
            return httpx.Response(200, json=SNAPSHOT)
        if path == "/api/alarms/site/7/events":
            return httpx.Response(200, json=[CLEARED_EVENT, ACTIVE_EVENT])
        if path == "/api/sites/7/health":
            return httpx.Response(200, json=HEALTH)
        return httpx.Response(404, json={"detail": f"no fake route for {path}"})
