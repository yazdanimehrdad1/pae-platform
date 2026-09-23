from collections import defaultdict
from dataclasses import dataclass

from utils.exceptions import ValidationError


@dataclass
class NativePointRange:
    name: str
    poll_kind: str
    address: int
    size: int


def validate_no_register_overlap(points: list[NativePointRange]) -> None:
    """
    Raises ValidationError if any two points share registers within the same poll_kind.
    Each point occupies [address, address + size - 1] inclusive.
    """
    by_kind: dict[str, list[NativePointRange]] = defaultdict(list)
    for p in points:
        by_kind[p.poll_kind].append(p)

    for kind, group in by_kind.items():
        sorted_group = sorted(group, key=lambda p: p.address)
        for i in range(1, len(sorted_group)):
            prev = sorted_group[i - 1]
            curr = sorted_group[i]
            prev_end = prev.address + prev.size - 1
            if curr.address <= prev_end:
                raise ValidationError(
                    f"Register overlap in '{kind}': "
                    f"'{prev.name}' occupies {prev.address}–{prev_end}, "
                    f"'{curr.name}' starts at {curr.address}"
                )
