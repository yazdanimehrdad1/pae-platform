"""Device-file conventions, checked statically (no server, no network).

Invariant guarded: the conventions a new device file must follow, so the
``add-mock-device`` skill has a mechanical "done" check:

* unit_ids are unique across devices (the aggregator addresses devices by unit_id);
* every register sits inside its device's 100-wide band — holding
  ``(unit_id-1)*100 + 1 .. +99``, input ``1000 + (unit_id-1)*100 + 1 .. +99`` — and a
  32-bit register's low word does too;
* every register states ``type=`` explicitly (an absent type reads as "nobody decided");
* each device's blocks build, which is where profile_static coverage and 32-bit
  overlaps are validated.
"""

from __future__ import annotations

import pytest

from app.datastore import build_device_blocks
from app.modbus_mock_data import DEVICES
from app.models import DeviceSpec, RegisterSpec
from app.server import _static_profile_for

BAND_WIDTH = 100
INPUT_BAND_OFFSET = 1000


def _band(device: DeviceSpec, file_name: str) -> range:
    base = (device.unit_id - 1) * BAND_WIDTH + (INPUT_BAND_OFFSET if file_name == "input" else 0)
    # Start at base + 1: under the default ZERO_MODE=false no wire address reaches key `base`.
    return range(base + 1, base + BAND_WIDTH)


def _register_maps(device: DeviceSpec) -> list[tuple[str, dict[int, RegisterSpec]]]:
    return [("holding", device.holding_registers), ("input", device.input_registers)]


def test_at_least_one_device_is_discovered() -> None:
    assert DEVICES


def test_unit_ids_are_unique() -> None:
    unit_ids = [device.unit_id for device in DEVICES]
    assert len(unit_ids) == len(set(unit_ids)), unit_ids


@pytest.mark.parametrize("device", DEVICES, ids=lambda device: device.name)
class TestDeviceFile:
    def test_registers_stay_inside_the_device_band(self, device: DeviceSpec) -> None:
        outside = []
        for file_name, register_map in _register_maps(device):
            band = _band(device, file_name)
            for key, spec in register_map.items():
                last_address = key + 1 if spec.width == 32 else key
                if key not in band or last_address not in band:
                    occupies = f"{key}-{last_address}" if spec.width == 32 else f"{key}"
                    outside.append(
                        f"{file_name} {spec.name} occupies {occupies}, "
                        f"band is {band.start}-{band.stop - 1}"
                    )
        assert not outside, outside

    def test_every_register_states_its_type(self, device: DeviceSpec) -> None:
        implicit = [
            f"{file_name} {key} ({spec.name})"
            for file_name, register_map in _register_maps(device)
            for key, spec in register_map.items()
            if "type" not in spec.model_fields_set
        ]
        assert not implicit, implicit

    def test_blocks_build(self, device: DeviceSpec) -> None:
        build_device_blocks(
            device.holding_registers,
            device.input_registers,
            static_profile=_static_profile_for(device),
        )
