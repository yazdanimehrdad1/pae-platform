"""Middleware for validating time range query params."""

from fastapi import Request
from fastapi.responses import JSONResponse

from helpers.common.date_time import parse_iso_datetime


# TODO : take care of datetime format
async def validate_time_range(request: Request, call_next):
    start_time = request.query_params.get("start_time")
    end_time = request.query_params.get("end_time")

    if start_time and end_time:
        start_dt = parse_iso_datetime(start_time)
        end_dt = parse_iso_datetime(end_time)
        if start_dt is None or end_dt is None:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "Invalid time format. Expected ISO format (e.g., '2025-01-18T08:00:00Z')"
                },
            )
        # Only order-check bounds of the same kind. A mixed pair (one with an offset,
        # one without) raises TypeError if compared, and this middleware has no tz
        # context to reconcile them — the endpoint normalizes and reports that case.
        comparable = (start_dt.tzinfo is None) == (end_dt.tzinfo is None)
        if comparable and start_dt > end_dt:
            return JSONResponse(
                status_code=400,
                content={"detail": "start_time must be less than or equal to end_time"},
            )

    return await call_next(request)
