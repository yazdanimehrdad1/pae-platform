"""Fake site data connector over the fictional sites (USE_FAKE_DATA=true, tests).

Values come from a small plant model: each point's signal is a pure function of time, and
derived signals (inverter status, alarm words, fault codes, POI sums) read other points.
"""

import math
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from intelli_gateway.fake_data.models import AlarmRule, FakePoint, FakeSite, SignalShape
from intelli_gateway.fake_data.sites import FAKE_SITES
from intelli_gateway.schemas.site_data import (
    ActiveAlarms,
    ActivePointAlarm,
    AlarmEvent,
    Device,
    DeviceComms,
    HistorySample,
    PointClass,
    PointInfo,
    PointValue,
    Site,
    StateChange,
    Topology,
)

HISTORY_STEP = timedelta(minutes=5)
_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)
# How far back alarm evaluation looks to find when an alarm active at `start` was raised.
_ALARM_LOOKBACK = timedelta(days=1)


def _solar_factor(at: datetime, phase_hours: float) -> float:
    hours = at.timestamp() / 3600 + phase_hours
    hour_of_day = hours % 24
    if not 6 <= hour_of_day <= 18:
        return 0.0
    clouds = 0.9 + 0.1 * math.sin(hours * 1.7)
    return math.sin(math.pi * (hour_of_day - 6) / 12) * clouds


def _grid(start: datetime, end: datetime) -> list[datetime]:
    """5-minute grid points in [start, end], like a historian with a fixed poll interval."""
    moment = _EPOCH + math.ceil((start - _EPOCH) / HISTORY_STEP) * HISTORY_STEP
    moments: list[datetime] = []
    while moment <= end:
        moments.append(moment)
        moment += HISTORY_STEP
    return moments


class PlantModel:
    """Evaluates the fake site's points at a moment."""

    def __init__(self, fake: FakeSite) -> None:
        self._points = {point.info.name: point for point in fake.points}

    def value(self, name: str, at: datetime) -> float:
        signal = self._points[name].signal
        hours = at.timestamp() / 3600 + signal.phase_hours
        hour_of_day = hours % 24
        match signal.shape:
            case SignalShape.SOLAR:
                return round(signal.amplitude * _solar_factor(at, signal.phase_hours), 2)
            case SignalShape.DAILY_SINE:
                swing = math.sin(2 * math.pi * (hour_of_day - 9) / 24)
                return round(signal.base + signal.amplitude * swing, 2)
            case SignalShape.STEADY:
                return round(signal.base + signal.amplitude * math.sin(hours * 2.3), 3)
            case SignalShape.CONSTANT:
                return signal.base
            case SignalShape.SUM:
                return round(signal.base * sum(self.value(src, at) for src in signal.sources), 2)
            case SignalShape.INVERTER_STATUS:
                temp = self.value(self._source(name), at)
                if temp >= signal.trip:
                    return 6  # FAULT
                if _solar_factor(at, signal.phase_hours) <= 0:
                    return 1  # SLEEPING
                return 4 if temp >= signal.threshold else 3  # DERATED / RUNNING
            case SignalShape.INVERTER_POWER:
                status = self.value(self._source(name), at)
                available = signal.amplitude * _solar_factor(at, signal.phase_hours)
                if status == 3:
                    return round(available, 2)
                if status == 4:
                    return round(min(available, signal.limit), 2)
                return 0.0
            case SignalShape.ALARM_WORD:
                word = 0
                for rule in signal.bit_rules:
                    if self.value(rule.point, at) >= rule.at_or_above:
                        word |= 1 << rule.bit
                return word
            case SignalShape.FAULT_CODE:
                return signal.code if self.value(self._source(name), at) == signal.threshold else 0
            case SignalShape.BESS_STATE:
                power = self.value(self._source(name), at)
                return 2 if power < -50 else 3 if power > 50 else 1

    def _source(self, name: str) -> str:
        source = self._points[name].signal.source
        if source is None:
            raise ValueError(f"fake point {name} needs a source")
        return source


def _is_discrete(info: PointInfo) -> bool:
    """Status, alarm and fault-code points carry integer codes, not measurements."""
    return bool(info.enum_labels or info.bit_labels) or info.point_class in (
        PointClass.BINARY,
        PointClass.ALARM,
    )


def _labels(info: PointInfo, raw: float) -> tuple[str | None, list[str] | None]:
    code = int(raw)
    if info.bit_labels:
        return None, [label for bit, label in sorted(info.bit_labels.items()) if code >> bit & 1]
    if info.enum_labels:
        return info.enum_labels.get(code, "UNKNOWN"), None
    return None, None


class FakeSiteDataConnector:
    def __init__(
        self,
        sites: Sequence[FakeSite] = FAKE_SITES,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        stale_after_s: float = 600,
    ) -> None:
        self._sites = {fake.site.site_id: fake for fake in sites}
        self._models = {fake.site.site_id: PlantModel(fake) for fake in sites}
        self._clock = clock
        self._stale_after_s = stale_after_s

    # --- catalog ---

    async def list_sites(self) -> list[Site]:
        return [fake.site for fake in self._sites.values()]

    async def get_site(self, site_id: int) -> Site | None:
        fake = self._sites.get(site_id)
        return fake.site if fake else None

    async def list_devices(self, site_id: int) -> list[Device]:
        fake = self._sites.get(site_id)
        return list(fake.devices) if fake else []

    async def get_topology(self, site_id: int) -> Topology:
        fake = self._sites.get(site_id)
        return fake.topology if fake else Topology()

    async def list_points(self, site_id: int) -> list[PointInfo]:
        fake = self._sites.get(site_id)
        return [point.info for point in fake.points] if fake else []

    # --- readings ---

    async def get_latest_many(
        self, site_id: int, point_names: Sequence[str]
    ) -> dict[str, PointValue | None]:
        now = self._now()
        result: dict[str, PointValue | None] = {}
        for name in point_names:
            point = self._find(site_id, name)
            if point is None:
                result[name] = None
                continue
            at = self._last_reading_at(site_id, point.info.device_id, now)
            raw = self._models[site_id].value(name, at)
            label, active_bits = _labels(point.info, raw)
            age_s = (now - at).total_seconds()
            discrete = _is_discrete(point.info)
            result[name] = PointValue(
                name=name,
                device_id=point.info.device_id,
                value=int(raw) if discrete else raw,
                unit=point.info.unit,
                timestamp=at,
                quality="good",
                label=label,
                active_bits=active_bits,
                age_s=age_s,
                stale=age_s > self._stale_after_s,
            )
        return result

    async def get_history(
        self, site_id: int, point_name: str, start: datetime, end: datetime
    ) -> list[HistorySample] | None:
        point = self._find(site_id, point_name)
        if point is None:
            return None
        end = min(end, self._last_reading_at(site_id, point.info.device_id, self._now()))
        model = self._models[site_id]
        return [
            HistorySample(timestamp=moment, value=model.value(point_name, moment))
            for moment in _grid(start, end)
        ]

    async def get_state_changes(
        self, site_id: int, point_name: str, start: datetime, end: datetime
    ) -> list[StateChange] | None:
        point = self._find(site_id, point_name)
        if point is None:
            return None
        end = min(end, self._last_reading_at(site_id, point.info.device_id, self._now()))
        model = self._models[site_id]
        changes: list[StateChange] = []
        previous: int | None = None
        for moment in _grid(start, end):
            code = int(model.value(point_name, moment))
            if code != previous:
                label, active_bits = _labels(point.info, code)
                changes.append(
                    StateChange(timestamp=moment, value=code, label=label, active_bits=active_bits)
                )
                previous = code
        return changes

    # --- alarms and comms ---

    async def get_active_alarms(self, site_id: int) -> ActiveAlarms:
        now = self._now()
        events = [
            event
            for event in await self.get_alarm_events(site_id, now - HISTORY_STEP, now)
            if event.cleared_at is None
        ]
        fake = self._sites.get(site_id)
        point_alarms: list[ActivePointAlarm] = []
        if fake is not None:
            alarm_points = [p.info for p in fake.points if p.info.point_class is PointClass.ALARM]
            latest = await self.get_latest_many(site_id, [info.name for info in alarm_points])
            for info in alarm_points:
                reading = latest[info.name]
                if (
                    reading is None
                    or not isinstance(reading.value, int | float)
                    or not reading.value
                ):
                    continue
                point_alarms.append(
                    ActivePointAlarm(
                        point_name=info.name,
                        device_id=info.device_id,
                        severity=info.severity,
                        value=reading.value,
                        label=reading.label,
                        active_bits=reading.active_bits,
                        timestamp=reading.timestamp,
                    )
                )
        return ActiveAlarms(events=events, point_alarms=point_alarms)

    async def get_alarm_events(
        self, site_id: int, start: datetime, end: datetime, device_id: int | None = None
    ) -> list[AlarmEvent]:
        fake = self._sites.get(site_id)
        if fake is None:
            return []
        now = self._now()
        end = min(end, now)
        events: list[AlarmEvent] = []
        for rule in fake.alarm_rules:
            events.extend(self._rule_events(site_id, rule, start, end, now))
        for static in fake.static_events:
            raised = now - timedelta(hours=static.raised_hours_ago)
            cleared = (
                raised + timedelta(hours=static.duration_hours)
                if static.duration_hours is not None
                else None
            )
            if raised <= end and (cleared is None or cleared >= start):
                events.append(
                    AlarmEvent(
                        alarm_name=static.name,
                        severity=static.severity,
                        message=static.message,
                        device_id=static.device_id,
                        raised_at=raised,
                        cleared_at=cleared,
                    )
                )
        if device_id is not None:
            events = [event for event in events if event.device_id == device_id]
        return sorted(events, key=lambda event: event.raised_at)

    async def get_device_comms(self, site_id: int) -> list[DeviceComms]:
        now = self._now()
        comms: list[DeviceComms] = []
        for device in await self.list_devices(site_id):
            last = self._last_reading_at(site_id, device.device_id, now)
            comms.append(
                DeviceComms(
                    device_id=device.device_id,
                    last_reading_at=last,
                    stale=(now - last).total_seconds() > self._stale_after_s,
                )
            )
        return comms

    async def aclose(self) -> None:
        return None

    # --- helpers ---

    def _now(self) -> datetime:
        return self._clock().replace(second=0, microsecond=0)

    def _find(self, site_id: int, point_name: str) -> FakePoint | None:
        fake = self._sites.get(site_id)
        if fake is None:
            return None
        return next((point for point in fake.points if point.info.name == point_name), None)

    def _last_reading_at(self, site_id: int, device_id: int, now: datetime) -> datetime:
        stale_hours = self._sites[site_id].stale_devices.get(device_id)
        if stale_hours is None:
            return now
        return now - timedelta(hours=stale_hours)

    def _rule_events(
        self, site_id: int, rule: AlarmRule, start: datetime, end: datetime, now: datetime
    ) -> list[AlarmEvent]:
        """Replay the rule on the 5-minute grid; keep events that overlap [start, end]. Scans on
        to `now` so an event active at `end` gets its real clear time."""
        model = self._models[site_id]

        def active(at: datetime) -> bool:
            value = model.value(rule.point, at)
            if rule.bit is not None:
                return bool(int(value) >> rule.bit & 1)
            return rule.at_or_above is not None and value >= rule.at_or_above

        events: list[AlarmEvent] = []
        raised: datetime | None = None
        for moment in _grid(start - _ALARM_LOOKBACK, now):
            if raised is None and moment > end:
                break
            if active(moment):
                raised = raised or moment
            elif raised is not None:
                if moment >= start:
                    events.append(self._event(rule, raised, moment))
                raised = None
        if raised is not None:
            events.append(self._event(rule, raised, None))  # still active now
        return events

    @staticmethod
    def _event(rule: AlarmRule, raised: datetime, cleared: datetime | None) -> AlarmEvent:
        return AlarmEvent(
            alarm_name=rule.name,
            severity=rule.severity,
            message=rule.message,
            device_id=rule.device_id,
            raised_at=raised,
            cleared_at=cleared,
        )
