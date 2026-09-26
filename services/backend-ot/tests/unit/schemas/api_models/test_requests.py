"""
Unit tests for request validation in schemas.api_models.requests.

Guards that the API accepts exactly the supported data_type / device_type vocabulary,
that a point's size matches its data_type's register width, and that a point's optional
class / severity accept exactly their vocabulary in any casing, under the wire name "class".
"""

import pytest
from pydantic import ValidationError

from schemas.api_models.requests import (
    DeviceCreateRequest,
    DevicePointCreateRequest,
    DevicePointUpdateRequest,
)
from schemas.api_models.types import (
    SUPPORTED_DATA_TYPES,
    SUPPORTED_DEVICE_TYPES,
    SUPPORTED_POINT_CLASSES,
    SUPPORTED_SEVERITIES,
    register_size,
)


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

class TestPointClassAndSeverity:
    def _payload(self, **fields: str | None) -> dict[str, str | int | None]:
        return {"name": "test_point", "size": 1, "data_type": "uint16", **fields}

    def test_both_default_to_none(self):
        point = DevicePointCreateRequest.model_validate(self._payload())
        assert point.point_class is None
        assert point.severity is None

    @pytest.mark.parametrize("point_class", sorted(SUPPORTED_POINT_CLASSES))
    def test_every_class_accepted_under_wire_name(self, point_class: str):
        point = DevicePointCreateRequest.model_validate(self._payload(**{"class": point_class}))
        assert point.point_class == point_class

    @pytest.mark.parametrize("severity", sorted(SUPPORTED_SEVERITIES))
    def test_every_severity_accepted(self, severity: str):
        point = DevicePointCreateRequest.model_validate(self._payload(severity=severity))
        assert point.severity == severity

    @pytest.mark.parametrize("model", [DevicePointCreateRequest, DevicePointUpdateRequest])
    def test_casing_is_normalized(
        self, model: type[DevicePointCreateRequest] | type[DevicePointUpdateRequest]
    ):
        point = model.model_validate(self._payload(**{"class": "alarm", "severity": "High"}))
        assert point.point_class == "ALARM"
        assert point.severity == "HIGH"

    @pytest.mark.parametrize(
        "fields", [{"class": "METERING"}, {"class": ""}, {"severity": "CRITICAL"}]
    )
    def test_unknown_values_rejected(self, fields: dict[str, str]):
        with pytest.raises(ValidationError):
            DevicePointCreateRequest.model_validate(self._payload(**fields))

    def test_serializes_as_class_on_the_wire(self):
        point = DevicePointCreateRequest.model_validate(self._payload(**{"class": "ANALOG"}))
        assert point.model_dump(by_alias=True)["class"] == "ANALOG"
