"""The JSON format of a per-asset Modbus map (point name → register), its validation, and the
default layout generator. There is no Modbus server yet (see interfaces/modbus/README.md).

Each simulated asset can then appear to the EMS at its own unit ID (and port), like a real site
device. Engineering value = raw register value × scale.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from powerflow.points.definitions import (
    POI_ASSET_ID,
    POINT_LISTS,
    SITE_ASSET_ID,
    Access,
    AssetType,
    DataType,
    PointDef,
    PointSource,
    point_def,
)
from powerflow.site_config import SiteConfig


class RegisterType(StrEnum):
    HOLDING = "holding"
    INPUT = "input"
    COIL = "coil"
    DISCRETE_INPUT = "discrete_input"


class ModbusDataType(StrEnum):
    BOOL = "bool"  # coils / discrete inputs
    INT16 = "int16"
    UINT16 = "uint16"
    INT32 = "int32"
    UINT32 = "uint32"
    FLOAT32 = "float32"
    UINT64 = "uint64"


REGISTER_WIDTH: dict[ModbusDataType, int] = {
    ModbusDataType.BOOL: 1,
    ModbusDataType.INT16: 1,
    ModbusDataType.UINT16: 1,
    ModbusDataType.INT32: 2,
    ModbusDataType.UINT32: 2,
    ModbusDataType.FLOAT32: 2,
    ModbusDataType.UINT64: 4,
}
WRITABLE_REGISTERS = {RegisterType.HOLDING, RegisterType.COIL}
BIT_REGISTERS = {RegisterType.COIL, RegisterType.DISCRETE_INPUT}


class WordOrder(StrEnum):
    BIG = "big"  # high word first
    LITTLE = "little"  # low word first ("word swapped")


class ModbusPointMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point: str = Field(description="Point name from the asset type's point list.")
    register_type: RegisterType
    address: int = Field(ge=0, le=65535)
    data_type: ModbusDataType
    word_order: WordOrder = WordOrder.BIG
    scale: float = Field(default=1.0, description="Engineering value = raw × scale.")
    enum_values: dict[int, str] | None = Field(
        default=None, description="For a status enum: register value → state name."
    )
    bit_flags: dict[int, str] | None = Field(
        default=None, description="For an alarm/flag word: bit number (0 = LSB) → flag name."
    )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.scale == 0:
            raise ValueError(f"{self.point}: scale can't be 0")
        if self.enum_values is not None and self.bit_flags is not None:
            raise ValueError(f"{self.point}: a register is an enum or a bitfield, not both")
        sixteen_bit = self.data_type in (ModbusDataType.UINT16, ModbusDataType.INT16)
        if (self.enum_values is not None or self.bit_flags is not None) and not sixteen_bit:
            raise ValueError(f"{self.point}: enums and bitfields are 16-bit registers")
        if self.bit_flags is not None and not all(0 <= bit <= 15 for bit in self.bit_flags):
            raise ValueError(f"{self.point}: bit numbers are 0..15")
        is_bool = self.data_type is ModbusDataType.BOOL
        if is_bool != (self.register_type in BIT_REGISTERS):
            raise ValueError(f"{self.point}: bool goes with coils/discrete inputs only")
        if self.address + REGISTER_WIDTH[self.data_type] - 1 > 65535:
            raise ValueError(f"{self.point}: register range exceeds 65535")
        return self


class ModbusMap(BaseModel):
    """One asset's map. `asset` is `<asset_type>.<asset_id>`, e.g. `bess.bess1`."""

    model_config = ConfigDict(extra="forbid")

    map_version: Literal[1] = 1
    asset: str = Field(pattern=r"^(bess|pv|load|poi|site|meter)\.[A-Za-z0-9_-]+$")
    unit_id: int = Field(ge=1, le=247)
    port: int = Field(default=502, ge=1, le=65535)
    register_numbering: Literal["zero_based", "one_based"] = "zero_based"
    points: list[ModbusPointMap] = Field(min_length=1)

    @property
    def asset_type(self) -> AssetType:
        return AssetType(self.asset.split(".", 1)[0])

    @property
    def asset_id(self) -> str:
        return self.asset.split(".", 1)[1]

    @model_validator(mode="after")
    def _no_overlaps(self) -> Self:
        used: dict[tuple[RegisterType, int], str] = {}
        for entry in self.points:
            for offset in range(REGISTER_WIDTH[entry.data_type]):
                key = (entry.register_type, entry.address + offset)
                if key in used:
                    raise ValueError(
                        f"{entry.point} overlaps {used[key]} at {entry.register_type} "
                        f"{entry.address + offset}"
                    )
                used[key] = entry.point
        return self


def check_map_against_points(modbus_map: ModbusMap) -> list[str]:
    """Problems binding the map to the point list (empty = OK): unknown points, writable
    points that aren't on a writable register (or read-only points that are), and enum or
    bitfield meanings that differ from the point list's."""
    problems: list[str] = []
    for entry in modbus_map.points:
        definition = point_def(modbus_map.asset_type, entry.point)
        if definition is None:
            problems.append(f"{entry.point}: not a {modbus_map.asset_type} point")
            continue
        writable_register = entry.register_type in WRITABLE_REGISTERS
        if (definition.access is Access.READ_WRITE) != writable_register:
            problems.append(
                f"{entry.point}: access {definition.access} doesn't fit a "
                f"{entry.register_type} register"
            )
        if entry.enum_values is not None and entry.enum_values != definition.enum_values:
            problems.append(f"{entry.point}: enum_values differ from the point list")
        if entry.bit_flags is not None and entry.bit_flags != definition.bit_flags:
            problems.append(f"{entry.point}: bit_flags differ from the point list")
    return problems


DEFAULT_PORT = 502
# Nameplate points start here in the input registers, after the live measurements.
NAMEPLATE_BASE_ADDRESS = 100


def _register_format(point: PointDef) -> tuple[ModbusDataType, float]:
    """(register data type, scale) for a point: float32 values with a scale hint are packed as
    signed int32 at that resolution; the rest keep their natural integer type."""
    match point.data_type:
        case DataType.FLOAT32:
            if point.scale_hint is None:
                return ModbusDataType.FLOAT32, 1.0
            return ModbusDataType.INT32, point.scale_hint
        case DataType.UINT16 | DataType.ENUM16 | DataType.BITFIELD16:
            return ModbusDataType.UINT16, 1.0
        case DataType.UINT32:
            return ModbusDataType.UINT32, 1.0
        case DataType.UINT64:
            return ModbusDataType.UINT64, 1.0


def default_map(
    asset_type: AssetType, asset_id: str, unit_id: int, port: int = DEFAULT_PORT
) -> ModbusMap:
    """A map covering every point of the asset type, in point-list order:
    RW setpoints → holding registers from 0; everything else read-only → input registers from 0,
    except nameplate → input registers from NAMEPLATE_BASE_ADDRESS."""
    next_address = {"holding": 0, "input": 0, "nameplate": NAMEPLATE_BASE_ADDRESS}
    entries: list[ModbusPointMap] = []
    for point in POINT_LISTS[asset_type]:
        data_type, scale = _register_format(point)
        if point.access is Access.READ_WRITE:
            block, register_type = "holding", RegisterType.HOLDING
        elif point.source is PointSource.NAMEPLATE:
            block, register_type = "nameplate", RegisterType.INPUT
        else:
            block, register_type = "input", RegisterType.INPUT
        entries.append(
            ModbusPointMap(
                point=point.name,
                register_type=register_type,
                address=next_address[block],
                data_type=data_type,
                word_order=WordOrder.BIG,
                scale=scale,
                enum_values=point.enum_values,
                bit_flags=point.bit_flags,
            )
        )
        next_address[block] += REGISTER_WIDTH[data_type]
    if next_address["input"] > NAMEPLATE_BASE_ADDRESS:
        raise ValueError(f"{asset_type} measurements overflow into the nameplate block")
    # Defaults are set explicitly, so a stored map spells out its own layout.
    return ModbusMap(
        map_version=1,
        asset=f"{asset_type}.{asset_id}",
        unit_id=unit_id,
        port=port,
        register_numbering="zero_based",
        points=entries,
    )


def default_site_maps(config: SiteConfig, port: int = DEFAULT_PORT) -> list[ModbusMap]:
    """Default maps for every asset of a site. Unit IDs run from 1 in the order BESS, PV,
    loads, POI meter, site status, feeder meters (last, so adding meters moves no unit ID)."""
    assets = [
        *[(AssetType.BESS, bess.id) for bess in config.bess],
        *[(AssetType.PV, pv.id) for pv in config.pv],
        *[(AssetType.LOAD, load.id) for load in config.loads],
        (AssetType.POI, POI_ASSET_ID),
        (AssetType.SITE, SITE_ASSET_ID),
        *[(AssetType.METER, meter.id) for meter in config.meters],
    ]
    return [
        default_map(asset_type, asset_id, unit_id, port)
        for unit_id, (asset_type, asset_id) in enumerate(assets, start=1)
    ]
