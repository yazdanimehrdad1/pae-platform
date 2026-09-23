"""
Unit tests for reading translation in helpers.reads.calculate_reads.

Guards that a decoded enum value translates to its label, and that a null reading
(failed decode) stays null.
"""

from helpers.modbus.modbus_data_mapping import _decode_modbus_point_value
from helpers.reads.calculate_reads import translate_reading


class TestEnumTranslation:
    ENUM_DETAIL = {"0": "OFF", "1": "ON", "2": "ERROR", "3": "HEALTHY"}

    def test_enum_point_decodes_then_translates(self):
        """The enum bug end to end: with a supported type, the label comes through."""
        decoded = _decode_modbus_point_value(register_values=[3], data_type="enum16")
        assert decoded.success is True
        assert translate_reading(decoded.value, None, self.ENUM_DETAIL) == "HEALTHY"

    def test_null_reading_translates_to_none(self):
        """A failed decode stores None, and no enum_detail can rescue it."""
        assert translate_reading(None, None, self.ENUM_DETAIL) is None
