"""
Unit tests for request validation in schemas.api_models.requests.

Guards that the API accepts exactly the supported data_type / device_type vocabulary,
that a point's size matches its data_type's register width, and that a point's optional
class / severity accept exactly their vocabulary in any casing, under the wire name "class",
that a new point records by default while an update or upsert that leaves record_enabled out
doesn't change it,
and that a site's time zone is stored as its canonical IANA name (unknown zones rejected).
"""

import pytest
from pydantic import ValidationError

from schemas.api_models.requests import (
    DeviceCreateRequest,
    DevicePointCreateRequest,
    DevicePointUpdateRequest,
    Location,
    SiteCreateRequest,
    SiteUpdateRequest,
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


class TestRecordEnabled:
    PAYLOAD: dict[str, str | int] = {"name": "test_point", "size": 1, "data_type": "uint16"}

    def test_a_new_point_records_by_default_and_the_default_is_not_marked_as_sent(self):
        point = DevicePointCreateRequest.model_validate(self.PAYLOAD)
        assert point.record_enabled is True
        # bulk upsert only changes an existing point's flag when it was sent.
        assert "record_enabled" not in point.model_fields_set

    def test_sent_false_is_marked_as_sent(self):
        point = DevicePointCreateRequest.model_validate(self.PAYLOAD | {"record_enabled": False})
        assert point.record_enabled is False
        assert "record_enabled" in point.model_fields_set

    def test_an_update_leaves_it_unchanged_unless_sent(self):
        assert DevicePointUpdateRequest.model_validate({}).record_enabled is None

class TestSiteTimezone:
    def _create(self, **overrides: object) -> SiteCreateRequest:
        defaults = SiteCreateRequest(
            client_id="c",
            name="Site",
            location=Location(street="1 Main St", city="Fresno", state="CA", zip_code=93701),
            operator="op",
            capacity="1MW",
        )
        return SiteCreateRequest.model_validate(defaults.model_dump() | overrides)

    def test_create_defaults_to_utc(self):
        assert self._create().timezone == "UTC"

    def test_create_explicit_null_is_utc(self):
        assert self._create(timezone=None).timezone == "UTC"

    @pytest.mark.parametrize(
        ("typed", "canonical"),
        [
            ("America/Los_Angeles", "America/Los_Angeles"),
            ("america/los_angeles", "America/Los_Angeles"),
            ("  PT ", "America/Los_Angeles"),
            ("utc", "UTC"),
            ("Europe/Berlin", "Europe/Berlin"),
        ],
    )
    def test_create_stores_the_canonical_name(self, typed: str, canonical: str):
        assert self._create(timezone=typed).timezone == canonical

    @pytest.mark.parametrize("bad", ["Mars/Olympus_Mons", "CEST", "+02:00"])
    def test_create_rejects_an_unknown_zone(self, bad: str):
        with pytest.raises(ValidationError, match="Unknown timezone"):
            self._create(timezone=bad)

    def test_update_omitted_timezone_stays_unset(self):
        update = SiteUpdateRequest(operator="new")
        assert update.timezone is None
        assert "timezone" not in update.model_fields_set

    def test_update_canonicalizes_and_rejects_like_create(self):
        assert SiteUpdateRequest(timezone="et").timezone == "America/New_York"
        with pytest.raises(ValidationError, match="Unknown timezone"):
            SiteUpdateRequest(timezone="Nowhere/City")
