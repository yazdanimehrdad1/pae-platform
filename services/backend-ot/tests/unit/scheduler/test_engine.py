"""The alarm evaluation job runs on its own interval (ALARM_EVALUATION_INTERVAL_SECONDS), not the poll interval."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from apscheduler.triggers.interval import IntervalTrigger
from pydantic import ValidationError

import scheduler.engine as engine
from config import Settings


class RecordedJob:
    def __init__(self, job_id: str, trigger: IntervalTrigger) -> None:
        self.job_id = job_id
        self.trigger = trigger


def _record_jobs(monkeypatch: pytest.MonkeyPatch) -> list[RecordedJob]:
    recorded: list[RecordedJob] = []

    def fake_add_job(job_func: Callable, trigger: Any, job_id: str, name: str | None = None, **kwargs: Any) -> None:
        recorded.append(RecordedJob(job_id, trigger))

    monkeypatch.setattr(engine, "add_job", fake_add_job)
    return recorded


class TestAlarmEvaluationInterval:
    def test_default_is_22_seconds(self) -> None:
        assert Settings().alarm_evaluation_interval_seconds == 22

    def test_env_overrides_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALARM_EVALUATION_INTERVAL_SECONDS", "45")
        assert Settings().alarm_evaluation_interval_seconds == 45

    def test_rejects_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ALARM_EVALUATION_INTERVAL_SECONDS", "0")
        with pytest.raises(ValidationError):
            Settings()

    def test_job_uses_alarm_interval_not_poll_interval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(engine.settings, "alarm_evaluation_interval_seconds", 22)
        monkeypatch.setattr(engine.settings, "poll_interval_seconds", 10)
        recorded = _record_jobs(monkeypatch)

        engine._register_alarm_evaluation_job()

        (job,) = recorded
        assert job.job_id == "alarm_evaluation"
        assert isinstance(job.trigger, IntervalTrigger)
        assert job.trigger.interval == timedelta(seconds=22)

    def test_poll_job_keeps_poll_interval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(engine.settings, "alarm_evaluation_interval_seconds", 22)
        monkeypatch.setattr(engine.settings, "poll_interval_seconds", 10)
        recorded = _record_jobs(monkeypatch)

        engine._register_modbus_polling_job()

        (job,) = recorded
        assert job.job_id == "modbus_poll"
        assert job.trigger.interval == timedelta(seconds=10)
