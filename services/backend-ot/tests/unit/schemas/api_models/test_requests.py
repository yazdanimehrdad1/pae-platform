"""
Unit tests for request validation in schemas.api_models.requests.

Guards that the API accepts exactly the supported data_type / device_type vocabulary,
and that a point's size matches its data_type's register width.
"""

import pytest
from pydantic import ValidationError

from schemas.api_models.requests import DeviceCreateRequest, DevicePointCreateRequest
from schemas.api_models.types import SUPPORTED_DATA_TYPES, SUPPORTED_DEVICE_TYPES, register_size


class TestDataTypeValidation:
    def _payload(self, data_type: str, size: int) -> dict[str, str | int]:
        return {
            "name": "test_point",
            "poll_kind": "holding",
            "address": 1400,
            "size": size,
            "data_type": data_type,
        }

    @pytest.mark.parametrize("data_type", sorted(SUPPORTED_DATA_TYPES))
    def test_supported_type_accepted(self, data_type: str):
        payload = self._payload(data_type, register_size(data_type))
        assert DevicePointCreateRequest(**payload).data_type == data_type

    @pytest.mark.parametrize("data_type", ["enum", "bitfield", "status_word", "INT32", "bogus"])
    def test_unsupported_type_rejected(self, data_type: str):
        """Bare enum/bitfield/status_word no longer exist; wrong casing is also rejected."""
        with pytest.raises(ValidationError):
            DevicePointCreateRequest.model_validate(self._payload(data_type, 1))

    def test_size_must_match_type_width(self):
        """enum32 needs 2 registers; supplying size=1 is rejected."""
        with pytest.raises(ValidationError):
            DevicePointCreateRequest.model_validate(self._payload("enum32", 1))
        with pytest.raises(ValidationError):
            DevicePointCreateRequest.model_validate(self._payload("int32", 1))

    def test_size_matching_type_width_accepted(self):
        assert DevicePointCreateRequest.model_validate(self._payload("enum32", 2)).size == 2
        assert DevicePointCreateRequest.model_validate(self._payload("bitfield16", 1)).size == 1


class TestDeviceTypeValidation:
    def _payload(self, device_type: str) -> dict[str, str]:
        return {"name": "test_device", "type": device_type, "host": "127.0.0.1"}

    @pytest.mark.parametrize("given", ["relay", "RELAY", "Relay", "rElAy"])
    def test_casing_is_normalized(self, given: str):
        assert DeviceCreateRequest.model_validate(self._payload(given)).type == "RELAY"

    @pytest.mark.parametrize("device_type", sorted(SUPPORTED_DEVICE_TYPES))
    def test_every_supported_device_type_accepted(self, device_type: str):
        assert DeviceCreateRequest.model_validate(self._payload(device_type)).type == device_type

    @pytest.mark.parametrize("device_type", ["bogus", "SOLAR", ""])
    def test_unsupported_device_type_rejected(self, device_type: str):
        with pytest.raises(ValidationError):
            DeviceCreateRequest.model_validate(self._payload(device_type))
