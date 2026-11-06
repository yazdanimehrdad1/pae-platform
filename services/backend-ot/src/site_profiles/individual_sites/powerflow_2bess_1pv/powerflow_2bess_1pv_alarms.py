"""
Powerflow 2BESS 1PV's alarms in code (PROFILE alarms). Only the ones declared in profile.py exist.
Each check is async (ctx: AlarmContext) -> AlarmCheck and runs every evaluation cycle; the delays
before raising and clearing are declared with it in profile.py.

A check reads the latest readings of the NATIVE points it needs (powerflow's point-standard names,
on devices named as the powerflow seed names them) and decides with
powerflow_2bess_1pv_helper_functions. A reading older than input_max_gap() counts as missing, and a
check missing what it needs is not active: losing data is device_comm_loss's alarm, not a fault.

Thresholds come from the site's ratings (powerflow's 2bess_1pv: 2 x 2.5 MW / 10 MWh BESS with SoC
limits 5-95 %, 5 MWac PV, transformers 2750 / 2750 / 5500 kVA, POI 12.47 kV, 60 Hz).
"""

from collections.abc import Iterable
from datetime import timedelta

from helpers.reads.device_points_readings import (
    get_last_successful_poll_times,
    get_latest_readings_by_point_ids,
)
from helpers.virtual_points.resolve import input_max_gap
from schemas.api_models import DevicePointResponse
from schemas.site_profiles import AlarmCheck, AlarmContext
from schemas.site_profiles.individual_sites.powerflow_2bess_1pv import LatestPointValue
from site_profiles.individual_sites.powerflow_2bess_1pv.powerflow_2bess_1pv_helper_functions import (
    GRID_MODE_GRID_TIED,
    METER_POWER_FAILURE,
    PPC_DEVICE_COMM_LOSS,
    PPC_POI_METER_FAIL,
    bess_warnings,
    frequency_outside,
    has_bit,
    has_code,
    inverter_faulted,
    loading_pct,
    pv_derate_reasons,
    pv_performance_pct,
    pv_underperforming,
    set_bits,
    stale_device_ids,
    worst_voltage_deviation_pct,
)

PLANT_CONTROLLER = "2bess_1pv-plant_controller"
POI_METER = "2bess_1pv-poi_meter"
BESS1 = "2bess_1pv-bess1"
BESS2 = "2bess_1pv-bess2"
PV1 = "2bess_1pv-pv1"
BESS_DEVICES = (BESS1, BESS2)
# Each feeder meter and the rating of the transformer it measures (kVA).
TRANSFORMER_RATINGS_KVA = {
    "2bess_1pv-m_bess1": 2750.0,
    "2bess_1pv-m_bess2": 2750.0,
    "2bess_1pv-m_pv1": 5500.0,
}

POI_NOMINAL_KV = 12.47
POI_VOLTAGE_POINTS = ("PhVphAB", "PhVphBC", "PhVphCA")
POI_VOLTAGE_WARNING_PCT = 5.0  # ANSI C84.1 Range A
POI_VOLTAGE_CRITICAL_PCT = 10.0
POI_MIN_HZ = 59.3  # IEEE 1547 trip region
POI_MAX_HZ = 60.5
SOC_LOW_PCT = 10.0  # the BESS SoC min (5 %) + 5
SOC_HIGH_PCT = 90.0  # the BESS SoC max (95 %) - 5
TRANSFORMER_OVERLOAD_PCT = 100.0
PV_RATED_KW = 5000.0
PV_DAYTIME_MIN_PCT = 5.0
PV_PERFORMANCE_MIN_PCT = 80.0
DEVICE_STALE_AFTER = timedelta(seconds=60)

PointKey = tuple[str, str]
"""(device name, point name)"""


def device_id_named(ctx: AlarmContext, name: str) -> int | None:
    return next((device.device_id for device in ctx.devices if device.name == name), None)


async def read_latest(
    ctx: AlarmContext, wanted: Iterable[PointKey]
) -> dict[PointKey, LatestPointValue]:
    """The fresh latest reading of each wanted point, with a bitfield's set bits. A point the site
    doesn't have, one that never reported, and a reading older than input_max_gap() are left out."""
    devices = {device.name: device for device in ctx.devices}
    points: dict[int, tuple[PointKey, DevicePointResponse]] = {}
    for device_name, point_name in wanted:
        device = devices.get(device_name)
        found = ctx.points_named(point_name, [device]) if device is not None else []
        if found:
            points[found[0].id] = ((device_name, point_name), found[0])
    if not points:
        return {}
    readings = await get_latest_readings_by_point_ids(list(points), site_id=ctx.site.site_id)
    oldest = ctx.now - input_max_gap()
    latest: dict[PointKey, LatestPointValue] = {}
    for reading in readings:
        entry = points.get(reading.device_point_id)
        if (
            entry is None
            or reading.derived_value is None
            or reading.timestamp is None
            or reading.timestamp < oldest
        ):
            continue
        key, point = entry
        latest[key] = LatestPointValue(
            value=reading.derived_value, bits=set_bits(reading.derived_value, point.bitfield_detail)
        )
    return latest


# --- Faults ---------------------------------------------------------------------------------------


async def _inverter_fault(ctx: AlarmContext, device: str, with_evt1: bool) -> AlarmCheck:
    names = ("InvSt", "Alrm", "Evt1") if with_evt1 else ("InvSt", "Alrm")
    latest = await read_latest(ctx, [(device, name) for name in names])
    inv_state = latest.get((device, "InvSt"))
    active = inverter_faulted(inv_state, latest.get((device, "Alrm")), latest.get((device, "Evt1")))
    return AlarmCheck(
        active=active,
        value=inv_state.value if inv_state else None,
        device_id=device_id_named(ctx, device),
    )


async def bess1_fault(ctx: AlarmContext) -> AlarmCheck:
    """BESS 1 is in FAULT, its breaker is open, or its battery reports a fault bit. value: InvSt."""
    return await _inverter_fault(ctx, BESS1, with_evt1=True)


async def bess2_fault(ctx: AlarmContext) -> AlarmCheck:
    """BESS 2 is in FAULT, its breaker is open, or its battery reports a fault bit. value: InvSt."""
    return await _inverter_fault(ctx, BESS2, with_evt1=True)


async def pv1_fault(ctx: AlarmContext) -> AlarmCheck:
    """PV 1 is in FAULT or its breaker is open. value: InvSt."""
    return await _inverter_fault(ctx, PV1, with_evt1=False)


async def poi_problem(ctx: AlarmContext) -> AlarmCheck:
    """The grid isn't there (GridMode not GRID_TIED), or the POI meter failed (the plant
    controller's POI_METER_FAIL, or the meter's own power-failure event). A grid problem is on the
    plant controller, with GridMode as value; a meter problem is on the POI meter."""
    latest = await read_latest(
        ctx, [(PLANT_CONTROLLER, "GridMode"), (PLANT_CONTROLLER, "Alrm"), (POI_METER, "Evt")]
    )
    grid_mode = latest.get((PLANT_CONTROLLER, "GridMode"))
    if grid_mode is not None and not has_code(grid_mode, GRID_MODE_GRID_TIED):
        return AlarmCheck(
            active=True, value=grid_mode.value, device_id=device_id_named(ctx, PLANT_CONTROLLER)
        )
    meter_failed = has_bit(latest.get((PLANT_CONTROLLER, "Alrm")), PPC_POI_METER_FAIL) or has_bit(
        latest.get((POI_METER, "Evt")), METER_POWER_FAILURE
    )
    return AlarmCheck(
        active=meter_failed, device_id=device_id_named(ctx, POI_METER) if meter_failed else None
    )


async def device_comm_loss(ctx: AlarmContext) -> AlarmCheck:
    """A device stopped answering: the plant controller reports DEVICE_COMM_LOSS, or backend-ot
    hasn't polled a device successfully for DEVICE_STALE_AFTER. value: how many devices backend-ot
    lost; device_id: that device when it is one."""
    latest = await read_latest(ctx, [(PLANT_CONTROLLER, "Alrm")])
    last_success = await get_last_successful_poll_times(
        [device.device_id for device in ctx.devices]
    )
    stale = stale_device_ids(last_success, ctx.now, DEVICE_STALE_AFTER)
    reported = has_bit(latest.get((PLANT_CONTROLLER, "Alrm")), PPC_DEVICE_COMM_LOSS)
    return AlarmCheck(
        active=reported or bool(stale),
        value=len(stale),
        device_id=stale[0] if len(stale) == 1 else None,
    )


async def _poi_voltage_deviation_pct(ctx: AlarmContext) -> float | None:
    latest = await read_latest(ctx, [(POI_METER, name) for name in POI_VOLTAGE_POINTS])
    return worst_voltage_deviation_pct([point.value for point in latest.values()], POI_NOMINAL_KV)


async def poi_voltage_critical(ctx: AlarmContext) -> AlarmCheck:
    """A POI line-to-line voltage is more than POI_VOLTAGE_CRITICAL_PCT from 12.47 kV.
    value: the worst deviation (%, signed)."""
    deviation = await _poi_voltage_deviation_pct(ctx)
    active = deviation is not None and abs(deviation) > POI_VOLTAGE_CRITICAL_PCT
    return AlarmCheck(active=active, value=deviation, device_id=device_id_named(ctx, POI_METER))


async def poi_voltage_out_of_range(ctx: AlarmContext) -> AlarmCheck:
    """A POI line-to-line voltage is outside ANSI C84.1 Range A (more than POI_VOLTAGE_WARNING_PCT
    from 12.47 kV) but not critical (poi_voltage_critical's). value: the worst deviation (%, signed)."""
    deviation = await _poi_voltage_deviation_pct(ctx)
    active = (
        deviation is not None
        and POI_VOLTAGE_WARNING_PCT < abs(deviation) <= POI_VOLTAGE_CRITICAL_PCT
    )
    return AlarmCheck(active=active, value=deviation, device_id=device_id_named(ctx, POI_METER))


async def poi_frequency_critical(ctx: AlarmContext) -> AlarmCheck:
    """The POI frequency is outside POI_MIN_HZ to POI_MAX_HZ. value: the frequency (Hz)."""
    hz = (await read_latest(ctx, [(POI_METER, "Hz")])).get((POI_METER, "Hz"))
    active = hz is not None and frequency_outside(hz.value, POI_MIN_HZ, POI_MAX_HZ)
    return AlarmCheck(
        active=active, value=hz.value if hz else None, device_id=device_id_named(ctx, POI_METER)
    )


# --- Warnings -------------------------------------------------------------------------------------


async def _bess_derated(ctx: AlarmContext, device: str) -> AlarmCheck:
    warnings = bess_warnings((await read_latest(ctx, [(device, "Evt1")])).get((device, "Evt1")))
    return AlarmCheck(
        active=bool(warnings), value=len(warnings), device_id=device_id_named(ctx, device)
    )


async def bess1_derated(ctx: AlarmContext) -> AlarmCheck:
    """BESS 1's battery reports a warning bit (over-temperature, fan, imbalance...). value: how many."""
    return await _bess_derated(ctx, BESS1)


async def bess2_derated(ctx: AlarmContext) -> AlarmCheck:
    """BESS 2's battery reports a warning bit (over-temperature, fan, imbalance...). value: how many."""
    return await _bess_derated(ctx, BESS2)


async def pv1_derated(ctx: AlarmContext) -> AlarmCheck:
    """PV 1 runs derated: blown string fuse, over-temperature without a trip, or a DERATED throttle.
    value: how many of those reasons."""
    latest = await read_latest(ctx, [(PV1, "InvSt"), (PV1, "Alrm"), (PV1, "ThrotSrc")])
    reasons = pv_derate_reasons(
        latest.get((PV1, "InvSt")), latest.get((PV1, "Alrm")), latest.get((PV1, "ThrotSrc"))
    )
    return AlarmCheck(active=bool(reasons), value=len(reasons), device_id=device_id_named(ctx, PV1))


async def _bess_socs(ctx: AlarmContext) -> dict[str, float]:
    latest = await read_latest(ctx, [(device, "SoC") for device in BESS_DEVICES])
    return {device: point.value for (device, _), point in latest.items()}


async def bess_soc_low(ctx: AlarmContext) -> AlarmCheck:
    """A BESS's SoC is below SOC_LOW_PCT. value and device: the lowest SoC (%) and its BESS."""
    socs = await _bess_socs(ctx)
    if not socs:
        return AlarmCheck(active=False)
    device, soc = min(socs.items(), key=lambda item: item[1])
    return AlarmCheck(active=soc < SOC_LOW_PCT, value=soc, device_id=device_id_named(ctx, device))


async def bess_soc_high(ctx: AlarmContext) -> AlarmCheck:
    """A BESS's SoC is above SOC_HIGH_PCT. value and device: the highest SoC (%) and its BESS."""
    socs = await _bess_socs(ctx)
    if not socs:
        return AlarmCheck(active=False)
    device, soc = max(socs.items(), key=lambda item: item[1])
    return AlarmCheck(active=soc > SOC_HIGH_PCT, value=soc, device_id=device_id_named(ctx, device))


async def transformer_overload(ctx: AlarmContext) -> AlarmCheck:
    """An asset transformer carries more than its rating (its feeder meter's VA). value and device:
    the most loaded one's loading (%) and its feeder meter."""
    latest = await read_latest(ctx, [(meter, "VA") for meter in TRANSFORMER_RATINGS_KVA])
    loadings = {
        meter: loading_pct(point.value, TRANSFORMER_RATINGS_KVA[meter])
        for (meter, _), point in latest.items()
    }
    if not loadings:
        return AlarmCheck(active=False)
    meter, loading = max(loadings.items(), key=lambda item: item[1])
    return AlarmCheck(
        active=loading > TRANSFORMER_OVERLOAD_PCT,
        value=loading,
        device_id=device_id_named(ctx, meter),
    )


async def pv_underperformance(ctx: AlarmContext) -> AlarmCheck:
    """PV 1 runs unthrottled in daylight but produces less than PV_PERFORMANCE_MIN_PCT of its
    available power. value: produced / available (%)."""
    latest = await read_latest(
        ctx, [(PV1, "W"), (PV1, "WAvail"), (PV1, "ThrotSrc"), (PV1, "InvSt")]
    )
    power, available = latest.get((PV1, "W")), latest.get((PV1, "WAvail"))
    performance = (
        pv_performance_pct(power.value, available.value, PV_RATED_KW, PV_DAYTIME_MIN_PCT)
        if power is not None and available is not None
        else None
    )
    active = pv_underperforming(
        latest.get((PV1, "InvSt")),
        latest.get((PV1, "ThrotSrc")),
        performance,
        PV_PERFORMANCE_MIN_PCT,
    )
    return AlarmCheck(active=active, value=performance, device_id=device_id_named(ctx, PV1))
