"""
Mock data for local development and DB seeding.

Organized as:
  SITES         — site records
  DEVICES       — devices, keyed to their site by site_name
  DEVICE_POINTS — NATIVE device points per device, keyed by device name

Each point carries its own ``poll_kind``; the device's ``scan_ranges`` are
computed from these points by the seed script (see
``helpers.device_points.scan_range_computation.compute_device_scan_ranges``)
rather than being stored by hand.

Every record is the app's own request model, so invalid seed data (e.g. a data_type
that no longer exists) fails at import instead of at insert time.
"""

from schemas.api_models import (
    Coordinates,
    DeviceCreateRequest,
    DevicePointCreateRequest,
    Location,
    SiteCreateRequest,
)
from schemas.tests_models import SeedDevice

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
        description="Alpha dev site — SEL relays + BESS",
        coordinates=Coordinates(lat=32.7157, lng=-117.1611),
    ),
]

# ---------------------------------------------------------------------------
# Devices  (site_name is resolved to site.id by the seed script)
# ---------------------------------------------------------------------------

DEVICES: list[SeedDevice] = [
    # --- Alpha Solar Farm ---
    SeedDevice(
        site_name="Alpha Solar Farm",
        device=DeviceCreateRequest(
            name="alpha-sel-751-main",
            host="192.168.10.1",
            port=502,
            timeout=5.0,
            server_address=1,
            type="RELAY",
            vendor="SEL",
            model="SEL-751",
            protocol="Modbus",
            description="Main feeder protection relay",
            poll_enabled=True,
            read_from_aggregator=True,
        ),
    ),
]

# ---------------------------------------------------------------------------
# Device points  (keyed by device name)
#
# Each point def supports:
#   address          — starting register address (required)
#   name             — point name, unique per device (required)
#   poll_kind        — "holding" | "input" | "coils" (required for NATIVE points)
#   data_type        — see schemas.api_models.types.SUPPORTED_DATA_TYPES
#   size             — registers occupied (float32/int32 occupy 2)
#   scale_factor     — multiplier applied to the raw value
#   unit             — engineering unit, or None
#   bitfield_detail  — {bit index: label} for bitfield points
#   enum_detail      — {value: label} for enum points
# ---------------------------------------------------------------------------

DEVICE_POINTS: dict[str, list[DevicePointCreateRequest]] = {

    # -----------------------------------------------------------------------
    # alpha-sel-751-main
    #   Standard SEL-751 metering registers plus a status/fault bitfield block
    # -----------------------------------------------------------------------
    "alpha-sel-751-main": [
        DevicePointCreateRequest(address=1400, name="M_FREQ",  poll_kind="holding", data_type="uint16", size=1, scale_factor=0.01,  unit="Hz"),
        DevicePointCreateRequest(address=1401, name="M_FREQS", poll_kind="holding", data_type="uint16", size=1, scale_factor=0.01,  unit="Hz"),
        DevicePointCreateRequest(address=1402, name="M_IA",    poll_kind="holding", data_type="uint16", size=1, scale_factor=0.1,   unit="A"),
        DevicePointCreateRequest(address=1403, name="M_IB",    poll_kind="holding", data_type="uint16", size=1, scale_factor=0.1,   unit="A"),
        DevicePointCreateRequest(address=1404, name="M_IC",    poll_kind="holding", data_type="uint16", size=1, scale_factor=0.1,   unit="A"),
        DevicePointCreateRequest(address=1405, name="M_IG",    poll_kind="holding", data_type="uint16", size=1, scale_factor=0.1,   unit="A"),
        DevicePointCreateRequest(address=1406, name="M_P",     poll_kind="holding", data_type="uint16", size=1, scale_factor=0.001, unit="MW"),
        DevicePointCreateRequest(address=1407, name="M_PF",    poll_kind="holding", data_type="uint16", size=1, scale_factor=0.001, unit=None),
        DevicePointCreateRequest(address=1408, name="M_Q",     poll_kind="holding", data_type="uint16", size=1, scale_factor=0.001, unit="MVAR"),
        DevicePointCreateRequest(address=1409, name="M_S",     poll_kind="holding", data_type="uint16", size=1, scale_factor=0.001, unit="MVA"),
        DevicePointCreateRequest(address=1410, name="M_VAB",   poll_kind="holding", data_type="uint16", size=1, scale_factor=0.1,   unit="kV"),
        DevicePointCreateRequest(address=1411, name="M_VBC",   poll_kind="holding", data_type="uint16", size=1, scale_factor=0.1,   unit="kV"),
        DevicePointCreateRequest(address=1412, name="M_VCA",   poll_kind="holding", data_type="uint16", size=1, scale_factor=0.1,   unit="kV"),
        DevicePointCreateRequest(address=1413, name="M_VDC",   poll_kind="holding", data_type="uint16", size=1, scale_factor=0.1,   unit="kV"),
        DevicePointCreateRequest(address=1414, name="M_VS",    poll_kind="holding", data_type="uint16", size=1, scale_factor=0.1,   unit="kV"),
        DevicePointCreateRequest(
            address=1415,
            name="M_STATUS",
            poll_kind="holding",
            data_type="bitfield16",
            size=1,
            scale_factor=1.0,
            unit=None,
            bitfield_detail={"0": "Closed", "1": "Open", "2": "Fault", "3": "Alarm"},
        ),
        DevicePointCreateRequest(
            address=1416,
            name="M_FAULT",
            poll_kind="holding",
            data_type="bitfield16",
            size=1,
            scale_factor=1.0,
            unit=None,
            bitfield_detail={"0": "No Fault", "1": "Fault"},
        ),
    ],
}
