"""
Mock data for local development and DB seeding.

Organized as:
  SITES         — site records (hand-written)
  DEVICES       — devices, keyed to their site by site_name
  DEVICE_POINTS — NATIVE device points per device, keyed by device name
  virtual_points — VIRTUAL example points (hand-written), built once the input point IDs exist

DEVICES and DEVICE_POINTS are NOT hand-written: they are built from mock-modbus's published
register map, `contracts/modbus/mock-modbus.devices.json` (see `mock_modbus_seed.py`), so the
dev historian polls exactly the devices and registers the simulator serves. To change what
gets seeded, change the mock device files and run `make -C services/mock-modbus contract`.

Each point carries its own ``poll_kind``; the device's ``scan_ranges`` are
computed from these points by the seed script (see
``helpers.device_points.scan_range_computation.compute_device_scan_ranges``)
rather than being stored by hand.

Every record is the app's own request model, so invalid seed data (e.g. a data_type
that no longer exists) fails at import instead of at insert time.
"""

from collections.abc import Callable

from mock_modbus_seed import build_seed, default_contract_path, load_contract

from schemas.api_models import (
    Coordinates,
    DevicePointCreateRequest,
    Location,
    SiteCreateRequest,
    VirtualCalculationDefinition,
    VirtualCase,
    VirtualCondition,
    VirtualConditionDefinition,
    VirtualConditionGroup,
    VirtualPointCreateRequest,
)
from schemas.tests_models import SeedDevice, SeedVirtualPoint

# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------

SITES: list[SiteCreateRequest] = [
    SiteCreateRequest(
        client_id="alpha-corp",
        name="Alpha Solar Farm",
        location=Location(street="100 Solar Way", city="San Diego", state="CA", zip_code=92101),
        operator="PAE",
        capacity="5MW",
        description="Alpha dev site — the mock-modbus devices (PV inverter, BESS, PV plant)",
        coordinates=Coordinates(lat=32.7157, lng=-117.1611),
        profile="alpha_solar",
    ),
]

# ---------------------------------------------------------------------------
# Devices + device points — one per mock-modbus device / register, from the contract
# ---------------------------------------------------------------------------

DEVICES: list[SeedDevice]
DEVICE_POINTS: dict[str, list[DevicePointCreateRequest]]
DEVICES, DEVICE_POINTS = build_seed(load_contract(default_contract_path()), site_name=SITES[0].name)

# ---------------------------------------------------------------------------
# Virtual points — hand-written examples of both kinds, reading across devices
# ---------------------------------------------------------------------------


def virtual_points(point_id: Callable[[str, str], int]) -> list[SeedVirtualPoint]:
    """`point_id(device_name, point_name)` resolves an input; the seeder calls this after NATIVE."""
    pv, bess = "mock-device-1", "mock-device-2"
    return [
        SeedVirtualPoint(
            device_name=pv,
            point=VirtualPointCreateRequest(
                name="SITE_AC_POWER",
                unit="W",
                point_class="ANALOG",
                definition=VirtualCalculationDefinition(
                    kind="calculation",
                    function="sum",
                    inputs=[point_id(pv, "active_power"), point_id(bess, "inverter_output_power")],
                ),
            ),
        ),
        SeedVirtualPoint(
            device_name=bess,
            point=VirtualPointCreateRequest(
                name="BESS_READY",
                point_class="BINARY",
                definition=VirtualConditionDefinition(
                    kind="condition",
                    cases=[
                        VirtualCase(
                            output=2,
                            label="fault",
                            when=VirtualConditionGroup(match="any", items=[
                                VirtualCondition(point_id=point_id(bess, "battery_state"), operator="==", value=5),
                                VirtualCondition(point_id=point_id(bess, "alarm_status_flags"), operator="bit_set", bit=7),
                            ]),
                        ),
                        VirtualCase(
                            output=1,
                            label="ready",
                            when=VirtualConditionGroup(match="all", items=[
                                VirtualCondition(point_id=point_id(bess, "state_of_charge"), operator=">=", value=20),
                                VirtualCondition(point_id=point_id(bess, "system_control_flags"), operator="bit_set", bit=1),
                            ]),
                        ),
                    ],
                    default_output=0,
                    default_label="not ready",
                ),
            ),
        ),
    ]
