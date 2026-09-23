"""Shared test data for device point data_type tests."""

# Register count each type needs: 16-bit -> 1, 32-bit -> 2, 64-bit -> 4.
REGISTERS_FOR_TYPE = {
    "bool": 1,
    "uint16": 1,
    "int16": 1,
    "raw": 1,
    "enum16": 1,
    "bitfield16": 1,
    "status_word16": 1,
    "uint32": 2,
    "int32": 2,
    "float32": 2,
    "enum32": 2,
    "bitfield32": 2,
    "status_word32": 2,
    "uint64": 4,
    "int64": 4,
    "float64": 4,
}
