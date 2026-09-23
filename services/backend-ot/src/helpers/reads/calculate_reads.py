"""Helpers for calculating derived read values."""

from typing import Any

from schemas.api_models.types import BitfieldDetailMap, EnumDetailMap


def normalize_detail_keys(detail: BitfieldDetailMap | EnumDetailMap | None, prefix: str) -> dict[str, Any]:
    """
    Normalize detail keys to include a prefix like "bit-" or "enum-".

    Example:
    {"01": "Trip"} -> {"enum-01": "Trip"}
    {"bit-01": "Closed"} -> {"bit-01": "Closed"}
    """
    if not detail:
        return {}
    normalized: dict[str, Any] = {}
    for key, value in detail.items():
        normalized[key if key.startswith(prefix) else f"{prefix}{key}"] = value
    return normalized


def _parse_enum_detail(raw: str) -> tuple[int | None, str | None]:
    for separator in (":", "|", ","):
        if separator in raw:
            value_str, detail = raw.split(separator, 1)
            value_str = value_str.strip()
            detail = detail.strip()
            if value_str.isdigit():
                return int(value_str), detail or None
            return None, raw
    if raw.strip().isdigit():
        return int(raw.strip()), None
    return None, raw


def translate_enum_value(derived_value: float, enum_detail: EnumDetailMap) -> str | None:
    """
    Return the human-readable label for derived_value from an enum_detail map.

    Supports two formats:
    - Simple: {"0": "OFF", "1": "ON"}  — key is the register value
    - Embedded: {"s1": "1:OFF", "s2": "2:ON"}  — value encodes register value and label
    """
    target = int(derived_value)

    # Direct key lookup (most common format)
    direct = enum_detail.get(str(target))
    if direct is not None:
        # Value might itself be "label" or "value:label"; return the label part
        _, label = _parse_enum_detail(direct)
        return label if label else direct

    # Fallback: scan values for embedded "value:label" pairs
    for raw in enum_detail.values():
        parsed_value, parsed_label = _parse_enum_detail(raw)
        if parsed_value == target and parsed_label:
            return parsed_label

    return "UNKNOWN"


def translate_bitfield_to_named_map(
    derived_value: float,
    bitfield_detail: BitfieldDetailMap,
) -> dict[str, int]:
    """
    Returns {label: 0|1} for every named bit in bitfield_detail, ordered by bit position.
    Iterates only the named entries — no need to know total bit count.
    """
    int_value = int(derived_value)
    details = normalize_detail_keys(bitfield_detail, "bit-")
    result: dict[str, int] = {}
    for key, label in sorted(details.items()):
        try:
            bit_index = int(key.split("-", 1)[1])
            result[label] = (int_value >> bit_index) & 1
        except (IndexError, ValueError):
            continue
    return result


def translate_reading(
    derived_value: float | None,
    bitfield_detail: BitfieldDetailMap | None,
    enum_detail: EnumDetailMap | None,
) -> "dict[str, int] | str | None":
    """
    Translate a raw derived_value to a human-readable form using the point's detail maps.

    Returns {label: 0|1} for bitfield points, a label string for enum points,
    or None for numeric-only points or when derived_value is None.
    """
    if derived_value is None:
        return None
    if bitfield_detail:
        return translate_bitfield_to_named_map(derived_value, bitfield_detail)
    if enum_detail:
        return translate_enum_value(derived_value, enum_detail)
    return None
