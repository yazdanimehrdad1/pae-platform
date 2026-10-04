"""Protocol-neutral data layer: the latest snapshot + history, the latest setpoints and the
injected conditions.

Adapters read measurements from here and write setpoints through SetpointService; they never
touch asset models or the solver. Thread-safe: the engine publishes from a worker thread.
"""

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

from powerflow.conditions import Conditions
from powerflow.core.snapshot import Snapshot
from powerflow.core.step import Setpoints
from powerflow.errors import UnknownAssetError
from powerflow.models.bess import BessSetpoint
from powerflow.models.pv import PvSetpoint


class StateStore:
    def __init__(self, history_size: int) -> None:
        self._lock = threading.Lock()
        self._latest: Snapshot | None = None
        self._history: deque[Snapshot] = deque(maxlen=history_size)

    @property
    def latest(self) -> Snapshot | None:
        return self._latest

    @property
    def history_size(self) -> int:
        return self._history.maxlen or 0

    def __len__(self) -> int:
        return len(self._history)

    def publish(self, snapshot: Snapshot) -> None:
        with self._lock:
            self._history.append(snapshot)
            self._latest = snapshot

    def history(self, start: datetime | None = None, end: datetime | None = None) -> list[Snapshot]:
        """Snapshots with start ≤ sim_time ≤ end (either bound optional), oldest first."""
        with self._lock:
            snapshots = list(self._history)
        return [
            snapshot
            for snapshot in snapshots
            if (start is None or snapshot.sim_time >= start)
            and (end is None or snapshot.sim_time <= end)
        ]

    def clear(self, history_size: int | None = None) -> None:
        with self._lock:
            self._latest = None
            self._history = deque(maxlen=history_size or self._history.maxlen)


class SetpointStore:
    """The setpoint each asset will apply on the next step (already validated and clamped)."""

    def __init__(self, setpoints: Setpoints) -> None:
        self._lock = threading.Lock()
        self._setpoints = setpoints

    def snapshot(self) -> Setpoints:
        with self._lock:
            return Setpoints(bess=dict(self._setpoints.bess), pv=dict(self._setpoints.pv))

    def replace_all(self, setpoints: Setpoints) -> None:
        with self._lock:
            self._setpoints = setpoints

    def bess(self, asset_id: str) -> BessSetpoint:
        with self._lock:
            if asset_id not in self._setpoints.bess:
                raise UnknownAssetError(f"no BESS {asset_id!r}")
            return self._setpoints.bess[asset_id]

    def pv(self, asset_id: str) -> PvSetpoint:
        with self._lock:
            if asset_id not in self._setpoints.pv:
                raise UnknownAssetError(f"no PV {asset_id!r}")
            return self._setpoints.pv[asset_id]

    def set_bess(self, asset_id: str, setpoint: BessSetpoint) -> None:
        with self._lock:
            if asset_id not in self._setpoints.bess:
                raise UnknownAssetError(f"no BESS {asset_id!r}")
            self._setpoints = replace(
                self._setpoints, bess={**self._setpoints.bess, asset_id: setpoint}
            )

    def set_pv(self, asset_id: str, setpoint: PvSetpoint) -> None:
        with self._lock:
            if asset_id not in self._setpoints.pv:
                raise UnknownAssetError(f"no PV {asset_id!r}")
            self._setpoints = replace(
                self._setpoints, pv={**self._setpoints.pv, asset_id: setpoint}
            )


class ConditionStore:
    """The injected conditions the next step applies (breakers, faults, comm loss, grid)."""

    def __init__(self, conditions: Conditions) -> None:
        self._lock = threading.Lock()
        self._conditions = conditions

    def snapshot(self) -> Conditions:
        with self._lock:
            return self._conditions

    def replace_all(self, conditions: Conditions) -> None:
        with self._lock:
            self._conditions = conditions

    def update(self, change: Callable[[Conditions], Conditions]) -> Conditions:
        with self._lock:
            self._conditions = change(self._conditions)
            return self._conditions
