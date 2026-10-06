"""PointRegistry: read and write any point by its full name (`bess.bess1.soc_pct`).

The protocol-neutral read surface: the Modbus server reads setpoint and nameplate values through
it, and HTTP lists and reads points with it. `write` (through SetpointService, so validated and
clamped exactly like HTTP setpoints) is the path for a writable protocol adapter.
"""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import ValidationError

from powerflow.core.engine import Engine
from powerflow.core.setpoints import (
    BessSetpointRequest,
    PvSetpointRequest,
    SetpointResult,
    SetpointService,
)
from powerflow.core.snapshot import Snapshot
from powerflow.errors import (
    NoMeasurementError,
    PointAccessError,
    SetpointError,
    UnknownAssetError,
    UnknownPointError,
)
from powerflow.models.bess import BESS_MODE_CODES
from powerflow.models.status import site_alarms
from powerflow.points.definitions import (
    POI_ASSET_ID,
    POINT_LISTS,
    RUN_STATE_CODES,
    SITE_ASSET_ID,
    Access,
    AssetType,
    PointDef,
    PointSource,
    point_def,
)

PointValue = float | int | bool
BESS_MODES_BY_CODE = {code: mode for mode, code in BESS_MODE_CODES.items()}


@dataclass(frozen=True)
class PointAddress:
    asset_type: AssetType
    asset_id: str
    point: str

    @classmethod
    def parse(cls, name: str) -> "PointAddress":
        parts = name.split(".")
        if len(parts) != 3:
            raise UnknownPointError(f"{name!r}: expected <asset_type>.<asset_id>.<point>")
        try:
            asset_type = AssetType(parts[0])
        except ValueError as error:
            raise UnknownPointError(f"{name!r}: unknown asset type {parts[0]!r}") from error
        return cls(asset_type, parts[1], parts[2])

    def __str__(self) -> str:
        return f"{self.asset_type}.{self.asset_id}.{self.point}"


class PointRegistry:
    def __init__(self, engine: Engine, setpoints: SetpointService) -> None:
        self._engine = engine
        self._setpoints = setpoints

    # -- names -----------------------------------------------------------------------------

    def asset_ids(self, asset_type: AssetType) -> list[str]:
        runtime = self._engine.runtime
        match asset_type:
            case AssetType.BESS:
                return list(runtime.bess)
            case AssetType.PV:
                return list(runtime.pv)
            case AssetType.LOAD:
                return list(runtime.loads)
            case AssetType.POI:
                return [POI_ASSET_ID]
            case AssetType.SITE:
                return [SITE_ASSET_ID]
            case AssetType.METER:
                return [meter.id for meter in runtime.config.meters]

    def names(self, source: PointSource | None = None) -> list[str]:
        """Every point name for the current config (optionally only one source)."""
        return [
            f"{asset_type}.{asset_id}.{definition.name}"
            for asset_type, definitions in POINT_LISTS.items()
            for asset_id in self.asset_ids(asset_type)
            for definition in definitions
            if source is None or definition.source is source
        ]

    def resolve(self, name: str) -> tuple[PointAddress, PointDef]:
        address = PointAddress.parse(name)
        if address.asset_id not in self.asset_ids(address.asset_type):
            raise UnknownAssetError(f"{name!r}: no {address.asset_type} {address.asset_id!r}")
        definition = point_def(address.asset_type, address.point)
        if definition is None:
            raise UnknownPointError(f"{name!r}: no point {address.point!r}")
        return address, definition

    # -- read ------------------------------------------------------------------------------

    def read(self, name: str) -> PointValue:
        address, definition = self.resolve(name)
        match definition.source:
            case PointSource.MEASUREMENT:
                latest = self._engine.store.latest
                if latest is None:
                    raise NoMeasurementError("no step has run yet")
                return _measurement(latest, address)
            case PointSource.SETPOINT:
                return self._setpoint(address)
            case PointSource.NAMEPLATE:
                return self._nameplate(address)
            case PointSource.SIMULATION:
                return self._simulation(address)

    def read_from_snapshot(self, snapshot: Snapshot, name: str) -> PointValue:
        """A measurement point's value in a given (e.g. historical) snapshot."""
        address, definition = self.resolve(name)
        if definition.source is not PointSource.MEASUREMENT:
            raise PointAccessError(f"{name!r} is a {definition.source} point, not in snapshots")
        return _measurement(snapshot, address)

    def _setpoint(self, address: PointAddress) -> PointValue:
        if address.asset_type is AssetType.BESS:
            bess = self._engine.setpoints.bess(address.asset_id)
            readers: dict[str, Callable[[], PointValue]] = {
                "p_setpoint_kw": lambda: bess.p_kw,
                "q_setpoint_kvar": lambda: bess.q_kvar,
                "mode_cmd": lambda: BESS_MODE_CODES[bess.mode],
            }
        else:
            pv = self._setpoints.pv(address.asset_id)
            q_mode = self._engine.setpoints.pv(address.asset_id).q_mode
            readers = {
                "p_limit_kw": lambda: pv.p_limit_kw,
                "p_limit_pct": lambda: pv.p_limit_pct,
                "q_setpoint_kvar": lambda: pv.q_kvar,
                "pf_setpoint": lambda: pv.pf,
                "q_mode": lambda: int(q_mode),
            }
        return readers[address.point]()

    def _nameplate(self, address: PointAddress) -> PointValue:
        runtime = self._engine.runtime
        if address.asset_type is AssetType.BESS:
            config = runtime.bess_asset(address.asset_id).config
            values: dict[str, float] = {
                "p_rated_discharge_kw": config.inverter.p_discharge_max_kw,
                "p_rated_charge_kw": config.inverter.p_charge_max_kw,
                "s_rated_kva": config.inverter.s_rated_kva,
                "capacity_kwh": config.battery.capacity_kwh,
                "soc_min_pct": config.battery.soc_min_pct,
                "soc_max_pct": config.battery.soc_max_pct,
            }
        else:
            pv_config = runtime.pv_asset(address.asset_id).config
            values = {
                "dc_kwp": pv_config.dc_kwp,
                "p_max_kw": pv_config.inverter.p_max_kw,
                "s_rated_kva": pv_config.inverter.s_rated_kva,
            }
        return values[address.point]

    def _simulation(self, address: PointAddress) -> PointValue:
        status = self._engine.status()
        alarms = site_alarms(status.last_converged, status.overrun_count, status.test_mode)
        values: dict[str, PointValue] = {
            "state": RUN_STATE_CODES[status.state],
            "overrun_count": status.overrun_count,
            "alarm_flags": int(alarms),
        }
        return values[address.point]

    # -- write -----------------------------------------------------------------------------

    def write(self, name: str, value: float) -> SetpointResult:
        address, definition = self.resolve(name)
        if definition.access is not Access.READ_WRITE:
            raise PointAccessError(f"{name!r} is read-only")
        try:
            if address.asset_type is AssetType.BESS:
                return self._setpoints.write_bess(address.asset_id, _bess_request(address, value))
            return self._setpoints.write_pv(address.asset_id, _pv_request(address, value))
        except ValidationError as error:
            raise SetpointError(f"{name!r}: {error}") from error


def _bess_request(address: PointAddress, value: float) -> BessSetpointRequest:
    if address.point == "mode_cmd":
        if value not in BESS_MODES_BY_CODE:
            raise SetpointError(f"mode_cmd must be one of {sorted(BESS_MODES_BY_CODE)}")
        return BessSetpointRequest(mode=BESS_MODES_BY_CODE[int(value)])
    field = {"p_setpoint_kw": "p_kw", "q_setpoint_kvar": "q_kvar"}[address.point]
    return BessSetpointRequest.model_validate({field: value})


def _pv_request(address: PointAddress, value: float) -> PvSetpointRequest:
    field = {
        "p_limit_kw": "p_limit_kw",
        "p_limit_pct": "p_limit_pct",
        "q_setpoint_kvar": "q_kvar",
        "pf_setpoint": "pf",
    }[address.point]
    return PvSetpointRequest.model_validate({field: value})


def _measurement(snapshot: Snapshot, address: PointAddress) -> PointValue:
    match address.asset_type:
        case AssetType.SITE:
            values: dict[str, PointValue] = {
                "step_id": snapshot.step_id,
                "sim_time_epoch_s": int(snapshot.sim_time.timestamp()),
                "converged": int(snapshot.converged),
            }
            return values[address.point]
        case AssetType.POI:
            return getattr(snapshot.poi, address.point)
        case AssetType.BESS:
            items = snapshot.bess
        case AssetType.PV:
            items = snapshot.pv
        case AssetType.LOAD:
            items = snapshot.loads
        case AssetType.METER:
            items = snapshot.meters
    for item in items:
        if item.id == address.asset_id:
            return getattr(item, address.point)
    raise UnknownAssetError(f"{address}: asset not in this snapshot")
