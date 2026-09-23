"""
Unit tests for register decoding in helpers.modbus.modbus_data_mapping.

Guards the invariant that the `DataType` Literal accepted by the API and the decode
branches in `_decode_modbus_point_value` cannot drift apart. Drift is silent in
production: an unsupported data_type decodes to BAD_DATA_TYPE, stores a null reading
every poll, and the endpoint hides it via response_model_exclude_none.
"""

import pytest

from helpers.modbus.modbus_data_mapping import _decode_modbus_point_value
from schemas.api_models.types import SUPPORTED_DATA_TYPES
from unit.data_type_fixtures import REGISTERS_FOR_TYPE


class TestDataTypeDecoding:
    def test_every_supported_type_has_a_register_width(self):
        """REGISTERS_FOR_TYPE must cover the Literal, or the test below silently skips."""
        assert set(REGISTERS_FOR_TYPE) == set(SUPPORTED_DATA_TYPES)

    @pytest.mark.parametrize("data_type", sorted(SUPPORTED_DATA_TYPES))
    def test_supported_type_decodes(self, data_type: str):
        """Every type the API accepts must decode, or points using it store nulls forever."""
        result = _decode_modbus_point_value(
            register_values=[1] * REGISTERS_FOR_TYPE[data_type],
            data_type=data_type,
        )
        assert result.success is True, f"{data_type}: {result.quality} — {result.reason}"
        assert result.value is not None

    @pytest.mark.parametrize("data_type", ["enum", "bitfield", "status_word", "int24", ""])
    def test_unsupported_type_is_rejected_by_decoder(self, data_type: str):
        """Bare enum/bitfield/status_word were replaced by width-suffixed variants."""
        result = _decode_modbus_point_value(register_values=[1], data_type=data_type)
        assert result.success is False
        assert result.quality == "BAD_DATA_TYPE"
