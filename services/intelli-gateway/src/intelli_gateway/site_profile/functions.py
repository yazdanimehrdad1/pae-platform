"""Running an approved site function the way the AI gets it: one path for the
`run_site_function` tool and the admin's test-run, so the admin sees exactly what Claude sees.

backend-ot computes the function (intelli-gateway computes nothing itself); the gated connector
(site_profile/gate.py) refuses functions, devices and parameters that are not approved. Each
series in the result is summarized here (count, min, max, avg, first, last and a few evenly
spaced samples), so a long window never floods Claude's context.
"""

from datetime import timedelta

from pydantic import JsonValue

from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.schemas.site_data import SiteFunctionRun
from intelli_gateway.utils.exceptions import InvalidRequestError

# What backend-ot samples a series result down to before the summary (it keeps extremes).
FUNCTION_MAX_POINTS = 500


async def run_function(
    site_data: SiteDataConnector,
    site_id: int,
    run: SiteFunctionRun,
    max_days: int,
    sample_count: int,
) -> dict[str, JsonValue]:
    if run.end <= run.start:
        raise InvalidRequestError("the window's end must be after its start")
    if run.end - run.start > timedelta(days=max_days):
        raise InvalidRequestError(f"the window is longer than {max_days} days; shorten it")
    result = await site_data.run_site_function(site_id, run, FUNCTION_MAX_POINTS)
    summarized = summarize_result(result, sample_count)
    return summarized if isinstance(summarized, dict) else {"result": summarized}


def summarize_result(content: JsonValue, sample_count: int) -> JsonValue:
    """The result with every series (an object with a `timeseries` list) summarized."""
    if isinstance(content, list):
        return [summarize_result(item, sample_count) for item in content]
    if not isinstance(content, dict):
        return content
    summarized: dict[str, JsonValue] = {}
    for key, value in content.items():
        if key == "timeseries" and isinstance(value, list):
            summarized[key] = summarize_series(value, sample_count)
        else:
            summarized[key] = summarize_result(value, sample_count)
    return summarized


def summarize_series(samples: list[JsonValue], sample_count: int) -> dict[str, JsonValue]:
    """A backend-ot series ([{time, value}, ...]) as count/min/max/avg/first/last and up to
    sample_count evenly spaced samples. Samples without a number are skipped."""
    points: list[tuple[str, float]] = []
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        time, value = sample.get("time"), sample.get("value")
        if isinstance(time, str) and isinstance(value, int | float) and not isinstance(value, bool):
            points.append((time, float(value)))
    if not points:
        return {"count": 0}
    values = [value for _, value in points]
    if len(points) <= sample_count:
        picked = points
    else:
        step = (len(points) - 1) / (sample_count - 1)
        picked = [points[round(index * step)] for index in range(sample_count)]

    def sample_json(point: tuple[str, float]) -> dict[str, JsonValue]:
        return {"timestamp": point[0], "value": point[1]}

    return {
        "count": len(points),
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 3),
        "first": sample_json(points[0]),
        "last": sample_json(points[-1]),
        "samples": [sample_json(point) for point in picked],
    }
