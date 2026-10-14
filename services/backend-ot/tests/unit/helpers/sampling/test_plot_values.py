"""Unit tests for helpers.sampling.plot_values (sampling one series for a chart).

Invariants guarded:
- up to 3 days a chart gets every sample, unchanged;
- beyond, plot values are a subset of the real samples (nothing averaged or invented), at most
  max_points of them, keeping each slice's first, last, lowest and highest (so spikes survive)
  and, for enum/bit points, every change of value;
- an outage (a gap longer than max_gap) breaks the line: both edges are kept and a gap marker
  (value None) sits at its midpoint, whatever the window length;
- without max_points nothing changes.
"""

from datetime import UTC, datetime, timedelta

from helpers.sampling.plot_values import (
    is_discrete,
    sample_point_timeseries,
    sample_readings,
    sample_series,
    sample_series_response,
)
from schemas.api_models import PointTimeseries, TimeseriesPoint
from schemas.internal_models import PointReading
from schemas.site_profiles import EnergySeriesResult

START = datetime(2026, 1, 15, tzinfo=UTC)
STEP = timedelta(seconds=10)
GAP = timedelta(seconds=30)
WEEK = timedelta(days=7)


def dense(count: int, value=lambda index: float(index % 100), step: timedelta = STEP) -> list[TimeseriesPoint]:
    return [TimeseriesPoint(time=START + step * index, value=value(index)) for index in range(count)]


def real(samples: list[TimeseriesPoint]) -> list[TimeseriesPoint]:
    return [sample for sample in samples if sample.value is not None]


def markers(samples: list[TimeseriesPoint]) -> list[TimeseriesPoint]:
    return [sample for sample in samples if sample.value is None]


class TestRawWindows:
    def test_up_to_three_days_every_sample_is_kept_unchanged(self):
        samples = dense(25_920)  # 3 days at 10 s
        sampled = sample_series(samples, START, START + timedelta(days=3), 2000, GAP, discrete=False)
        assert sampled == samples

    def test_without_max_points_samples_are_returned_as_given(self):
        samples = list(reversed(dense(10)))
        assert sample_series(samples, START, START + WEEK, None, GAP, discrete=False) is samples

    def test_a_raw_window_still_gets_gap_markers(self):
        samples = dense(3) + [TimeseriesPoint(time=START + timedelta(minutes=10), value=5.0)]
        sampled = sample_series(samples, START, START + timedelta(hours=1), 2000, GAP, discrete=False)
        assert real(sampled) == samples
        (marker,) = markers(sampled)
        assert marker.time == START + STEP * 2 + (timedelta(minutes=10) - STEP * 2) / 2


class TestPlotValues:
    def test_only_real_samples_at_most_max_points(self):
        samples = dense(60_480)  # a week at 10 s
        sampled = sample_series(samples, START, START + WEEK, 2000, GAP, discrete=False)
        assert 0 < len(sampled) <= 2000
        originals = {(sample.time, sample.value) for sample in samples}
        assert all((sample.time, sample.value) in originals for sample in sampled)
        assert [sample.time for sample in sampled] == sorted({sample.time for sample in sampled})

    def test_a_spike_inside_a_slice_survives(self):
        samples = dense(60_480, value=lambda index: 1000.0 if index == 30_011 else 1.0)
        sampled = sample_series(samples, START, START + WEEK, 2000, GAP, discrete=False)
        assert max(sample.value for sample in sampled) == 1000.0
        assert min(sample.value for sample in sampled) == 1.0

    def test_an_outage_keeps_both_edges_and_gets_a_marker(self):
        before = dense(30_000)
        after = [TimeseriesPoint(time=before[-1].time + timedelta(hours=5) + STEP * index, value=1.0) for index in range(30_000)]
        sampled = sample_series(before + after, START, START + WEEK, 2000, GAP, discrete=False)
        (marker,) = markers(sampled)
        assert before[-1].time < marker.time < after[0].time
        times = [sample.time for sample in sampled]
        assert before[-1].time in times and after[0].time in times

    def test_discrete_points_keep_every_change_of_value(self):
        # a state that changes every 997 samples: 60 changes in the week, all kept
        samples = dense(60_480, value=lambda index: float((index // 997) % 3))
        sampled = sample_series(samples, START, START + WEEK, 400, GAP, discrete=True)
        changes = [current for previous, current in zip(samples, samples[1:], strict=False) if current.value != previous.value]
        kept = {sample.time for sample in sampled}
        assert all(change.time in kept for change in changes)
        assert len(sampled) < len(samples)

    def test_null_samples_are_not_plot_values(self):
        samples = dense(60_480, value=lambda index: None if index % 2 else 1.0)
        sampled = sample_series(samples, START, START + WEEK, 2000, GAP, discrete=False)
        assert markers(sampled) == []


class TestDiscreteTypes:
    def test_enum_bitfield_status_word_and_bool_are_discrete(self):
        for data_type in ("enum16", "enum32", "bitfield16", "bitfield32", "status_word16", "status_word32", "bool"):
            assert is_discrete(data_type)
        for data_type in ("float32", "int16", "uint32", "raw"):
            assert not is_discrete(data_type)


def reading(point_id: int, time: datetime, value: float | None, data_type: str = "float32") -> PointReading:
    return PointReading(
        device_point_id=point_id, register_address=0, name=f"p{point_id}", data_type=data_type,
        size=2, timestamp=time, derived_value=value,
    )


class TestSampleReadings:
    def test_each_point_newest_first_with_its_metadata_and_markers(self):
        readings = [reading(2, START + STEP * index, 1.0) for index in range(3)]
        readings += [reading(1, START, 1.0), reading(1, START + timedelta(minutes=5), 2.0)]
        sampled = sample_readings(readings, START, START + timedelta(hours=1), 2000, GAP)
        assert [(item.device_point_id, item.derived_value) for item in sampled] == [
            (1, 2.0), (1, None), (1, 1.0), (2, 1.0), (2, 1.0), (2, 1.0),
        ]
        assert all(item.name == f"p{item.device_point_id}" for item in sampled)
        assert [item.timestamp for item in sampled if item.device_point_id == 2] == [START + STEP * 2, START + STEP, START]

    def test_without_max_points_readings_are_untouched(self):
        readings = [reading(1, START, 1.0)]
        assert sample_readings(readings, START, START + WEEK, None, GAP) is readings


class TestSampleSeriesResponse:
    def test_samples_every_series_of_a_list_and_updates_counts(self):
        series = PointTimeseries(id=0, name="site energy", data_type="float32", timeseries=dense(60_480), count=60_480)
        response = EnergySeriesResult(site_id=1, start_time=START, end_time=START + WEEK, energy_kwh=1.0, series=[series, series])
        sampled = sample_series_response(response, START, START + WEEK, 2000, GAP)
        assert all(0 < entry.count <= 2000 and entry.count == len(entry.timeseries) for entry in sampled.series)
        assert sampled.energy_kwh == 1.0

    def test_a_single_series_is_sampled_too(self):
        series = PointTimeseries(id=5, name="poi", data_type="float32", timeseries=dense(60_480), count=60_480)
        sampled = sample_point_timeseries(series, START, START + WEEK, 2000, GAP)
        assert 0 < sampled.count <= 2000
