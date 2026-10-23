"""Which parts of an engineer's point guide apply to a reading. Pure functions, no I/O."""

from intelli_gateway.schemas.knowledge import (
    GuideSeverity,
    LimitGuide,
    PointGuide,
    StateGuide,
    StateKind,
)
from intelli_gateway.schemas.site_data import PointValue

_SEVERITY_ORDER = {GuideSeverity.FAULT: 0, GuideSeverity.WARNING: 1, GuideSeverity.INFO: 2}


def applicable_guidance(guide: PointGuide, reading: PointValue) -> list[StateGuide | LimitGuide]:
    """Guide entries that match the reading, most severe first.

    - bitfield points: one entry per set bit that has a guide
    - enum and fault-code points: the entry for the current value (fault code 0 matches nothing
      unless the guide has an entry for it)
    - analog points: every limit the value is beyond
    """
    value = reading.value
    if isinstance(value, bool) or not isinstance(value, int | float):
        return []
    matches: list[StateGuide | LimitGuide] = []
    for state in guide.states:
        if state.kind is StateKind.BIT:
            if int(value) >> state.code & 1:
                matches.append(state)
        elif state.code == int(value):
            matches.append(state)
    matches.extend(limit for limit in guide.limits if limit.applies_to(float(value)))
    return sorted(matches, key=lambda entry: _SEVERITY_ORDER[entry.severity])
