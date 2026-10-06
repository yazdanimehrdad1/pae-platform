"""Engineering values → raw 16-bit registers, for the whole layout.

raw = round(value / scale), saturated to the data type's range. Signed types are two's
complement. 32/64-bit values are big-endian, high word first. Points nobody can serve, and
resolvers that return None, leave their registers at 0.
"""

import logging
import math

from powerflow.point_standard.calc import CALC_RESOLVERS
from powerflow.point_standard.catalog import PointRow, ServerSupport
from powerflow.point_standard.layout import Device, DeviceKind
from powerflow.point_standard.sources import Resolver, Sources
from powerflow.point_standard.values import DIRECT_RESOLVERS

logger = logging.getLogger(__name__)
WORD_BITS = 16
WORD_MASK = 0xFFFF


def resolver_for(kind: DeviceKind, row: PointRow) -> Resolver | None:
    """The resolver serving a point on this kind of device, per its `powerflow_server` value."""
    match row.support:
        case ServerSupport.YES:
            return DIRECT_RESOLVERS.get(kind, {}).get(row.point)
        case ServerSupport.CALC:
            return CALC_RESOLVERS.get(kind, {}).get(row.point)
        case ServerSupport.NO:
            return None


def encode(value: float, row: PointRow) -> list[int]:
    """The registers (uint16 each) for one value."""
    bits = row.width * WORD_BITS
    raw = round(value / row.scale) if math.isfinite(value) else 0
    if row.signed:
        low, high = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    else:
        low, high = 0, (1 << bits) - 1
    unsigned = min(max(raw, low), high) & ((1 << bits) - 1)
    return [(unsigned >> (WORD_BITS * index)) & WORD_MASK for index in reversed(range(row.width))]


def build_image(devices: tuple[Device, ...], sources: Sources) -> dict[int, int]:
    """address → raw register value, for every served point of every device."""
    image: dict[int, int] = {}
    for device in devices:
        for register in device.registers:
            resolver = resolver_for(device.kind, register.row)
            if resolver is None:
                continue
            value = resolver(sources, device)
            if value is None:
                continue
            for offset, word in enumerate(encode(float(value), register.row)):
                image[register.address + offset] = word
    return image
