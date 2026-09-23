"""
Unit tests for the data_type / device_type vocabulary in schemas.api_models.types.

Guards the nested-Literal flattening and register_size, which every other data_type
check (API validation, decoding) relies on.
"""

from schemas.api_models.types import (
    SUPPORTED_DATA_TYPES,
    SUPPORTED_DEVICE_TYPES,
    SUPPORTED_NUMERIC_DATA_TYPES,
    register_size,
)
from unit.data_type_fixtures import REGISTERS_FOR_TYPE


class TestLiteralComposition:
    """
    Guards the nested-Literal flattening in types.py. If PEP 586 flattening ever stops
    applying, get_args() returns Literal objects instead of strings and these sets go
    silently wrong — taking every other data_type check with them.
    """

    def test_set_sizes(self):
        assert len(SUPPORTED_NUMERIC_DATA_TYPES) == 10
        assert len(SUPPORTED_DATA_TYPES) == 16
        assert len(SUPPORTED_DEVICE_TYPES) == 10

    def test_all_members_are_strings(self):
        for value in SUPPORTED_DATA_TYPES | SUPPORTED_DEVICE_TYPES:
            assert isinstance(value, str)

    def test_numeric_is_a_subset_of_full(self):
        assert SUPPORTED_NUMERIC_DATA_TYPES < SUPPORTED_DATA_TYPES
        assert SUPPORTED_DATA_TYPES - SUPPORTED_NUMERIC_DATA_TYPES == {
            "enum16",
            "enum32",
            "bitfield16",
            "bitfield32",
            "status_word16",
            "status_word32",
        }


class TestRegisterSize:
    """register_size is the single source of width truth; it must cover the vocabulary."""

    def test_covers_every_supported_type(self):
        assert {t: register_size(t) for t in SUPPORTED_DATA_TYPES}.keys() == SUPPORTED_DATA_TYPES

    def test_matches_test_fixture(self):
        for data_type in SUPPORTED_DATA_TYPES:
            assert register_size(data_type) == REGISTERS_FOR_TYPE[data_type]

    def test_width_suffix_drives_size(self):
        assert register_size("enum16") == 1
        assert register_size("enum32") == 2
        assert register_size("bitfield16") == 1
        assert register_size("bitfield32") == 2
        assert register_size("status_word16") == 1
        assert register_size("status_word32") == 2
