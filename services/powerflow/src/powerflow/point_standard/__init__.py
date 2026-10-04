"""The PAE point standard (docs/point-standard/*.csv) on top of the simulation: which register each
point of each device occupies, and the value it holds. Everything that maps or calculates a
standard point lives in this package; the Modbus adapter only serves the resulting image.

- `catalog`: the CSVs (point lists, `powerflow_server` yes/calc/no, enum codes).
- `layout`: device chunks and addresses for a site.
- `values`: `yes` points (one powerflow value × a unit factor).
- `calc`: `calc` points (derived values).
- `registers`: engineering values → raw registers.
"""

from powerflow.point_standard.catalog import (
    PointRow,
    PointStandard,
    ServerSupport,
    load_point_standard,
)
from powerflow.point_standard.layout import (
    CHUNK_REGISTERS,
    POINT_LIST_FILE,
    REGISTER_SPACE,
    Device,
    DeviceKind,
    build_layout,
    device_template,
)
from powerflow.point_standard.registers import build_image, encode, resolver_for
from powerflow.point_standard.sources import PointValue, Sources

__all__ = [
    "CHUNK_REGISTERS",
    "POINT_LIST_FILE",
    "REGISTER_SPACE",
    "Device",
    "DeviceKind",
    "PointRow",
    "PointStandard",
    "PointValue",
    "ServerSupport",
    "Sources",
    "build_image",
    "build_layout",
    "device_template",
    "encode",
    "load_point_standard",
    "resolver_for",
]
