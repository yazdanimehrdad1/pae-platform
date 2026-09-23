"""Compute optimal Modbus scan ranges from a device's NATIVE points."""

from constants import MODBUS_MAX_REGISTERS_PER_READ
from schemas.api_models.requests import DeviceScanRanges, RegisterRange
from schemas.api_models.responses import DevicePointResponse

MAX_INTER_POINT_GAP = 10   # registers — gaps wider than this start a new range


def compute_device_scan_ranges(native_points: list[DevicePointResponse]) -> DeviceScanRanges:
    """
    Given all NATIVE points for a device, compute the optimal set of scan ranges.

    Groups by poll_kind, sorts by address, clusters into contiguous ranges splitting when:
    - The gap between the end of the previous point and the start of the next exceeds
      MAX_INTER_POINT_GAP, OR
    - Adding the next point would push the range beyond MODBUS_MAX_REGISTERS_PER_READ registers.
    """
    by_kind: dict[str, list[DevicePointResponse]] = {"holding": [], "input": [], "coils": []}

    for point in native_points:
        if point.poll_kind in by_kind:
            by_kind[point.poll_kind].append(point)

    result = DeviceScanRanges()

    for kind, points in by_kind.items():
        if not points:
            continue

        sorted_points = sorted(points, key=lambda p: p.address)
        ranges: list[RegisterRange] = []

        range_start = sorted_points[0].address
        range_end = sorted_points[0].address + sorted_points[0].size - 1

        for point in sorted_points[1:]:
            point_end = point.address + point.size - 1
            gap = point.address - range_end - 1
            proposed_size = point_end - range_start + 1

            if gap > MAX_INTER_POINT_GAP or proposed_size > MODBUS_MAX_REGISTERS_PER_READ:
                ranges.append(RegisterRange(
                    start_index=range_start,
                    count=range_end - range_start + 1,
                ))
                range_start = point.address
                range_end = point_end
            else:
                range_end = max(range_end, point_end)

        ranges.append(RegisterRange(
            start_index=range_start,
            count=range_end - range_start + 1,
        ))

        setattr(result, kind, ranges)

    return result
