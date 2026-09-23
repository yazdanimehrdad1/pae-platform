"""
Response models for endpoints that don't declare a `response_model` in the app.

TEST-ONLY: used by integration tests to parse these responses into typed objects. Each
mirrors what the router returns today. App code must never import `schemas.tests_models`.
When an endpoint gains a real `response_model`, move its model to
`schemas/api_models/responses.py` and delete it here.
"""

from typing import Literal

from pydantic import BaseModel

HealthStatus = Literal["healthy", "unhealthy"]


# --- Error bodies (AppError -> HTTPException in the routers) -------------------------------


class ApiErrorDetail(BaseModel):
    error: str
    message: str


class ApiErrorResponse(BaseModel):
    """`detail` is structured for AppError-derived errors, a plain string otherwise."""

    detail: ApiErrorDetail | str


# --- /api/cache/* --------------------------------------------------------------------------


class CacheHealthResponse(BaseModel):
    redis_connected: bool
    status: HealthStatus


class CacheSetResult(BaseModel):
    success: bool
    key: str
    message: str


class CacheDeleteResult(BaseModel):
    success: bool
    key: str
    message: str


class CacheExistsResult(BaseModel):
    key: str
    exists: bool


class CacheKeyEntry(BaseModel):
    key: str
    ttl: int | None


class CacheKeysResult(BaseModel):
    keys: list[CacheKeyEntry]
    count: int
    pattern: str


class CacheClearResult(BaseModel):
    success: bool
    deleted_count: int
    message: str


# --- /api/readyz, /api/redis_health, /api/db_health ---------------------------------------


class ReadinessChecks(BaseModel):
    database: bool
    redis: bool


class ReadinessResponse(BaseModel):
    ready: bool
    checks: ReadinessChecks


class RedisHealthResponse(BaseModel):
    status: HealthStatus
    connected: bool
    error: str | None = None


class DbServerInfo(BaseModel):
    postgresql_version: str
    database_name: str
    timescaledb_version: str | None = None


class DbHealthResponse(BaseModel):
    status: HealthStatus
    connected: bool
    error: str | None = None
    server_info: DbServerInfo | None = None
