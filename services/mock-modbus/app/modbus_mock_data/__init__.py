"""
Auto-discovers all device modules in this package and builds a DEVICES list.

Each device module must export a ``DEVICE`` attribute holding a fully-built
Pydantic :class:`~app.models.DeviceSpec` (its register maps are
``dict[int, RegisterSpec]``), so a malformed register map raises at import time
rather than during a client read. Modules without a ``DEVICE`` export are
skipped.

To add a new device, drop a new file (e.g. device_4.py) into this folder that
exports ``DEVICE = DeviceSpec(...)``. No other changes are needed.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from app.models import DeviceSpec

__all__ = ["DEVICES", "DeviceSpec"]

DEVICES: list[DeviceSpec] = []

_pkg_path = Path(__file__).parent

for _mod_info in pkgutil.iter_modules([str(_pkg_path)]):
    _mod = importlib.import_module(f"app.modbus_mock_data.{_mod_info.name}")
    _device = getattr(_mod, "DEVICE", None)
    if _device is None:
        continue  # not a device-definition module
    if not isinstance(_device, DeviceSpec):
        raise TypeError(
            f"{_mod_info.name}.DEVICE must be a DeviceSpec, "
            f"got {type(_device).__name__}"
        )
    DEVICES.append(_device)
