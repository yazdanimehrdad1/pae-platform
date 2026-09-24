"""
Models used ONLY by unit/integration tests and the dev seeder.

App code (api/, db/, helpers/, services/, ...) must never import from this package.
"""

from schemas.tests_models.api_responses import (
    ApiErrorDetail,
    ApiErrorResponse,
    CacheClearResult,
    CacheDeleteResult,
    CacheExistsResult,
    CacheHealthResponse,
    CacheKeyEntry,
    CacheKeysResult,
    CacheSetResult,
    DbHealthResponse,
    DbServerInfo,
    ReadinessChecks,
    ReadinessResponse,
    RedisHealthResponse,
)
from schemas.tests_models.mock_modbus_contract import (
    MockModbusContract,
    MockModbusDevice,
    MockModbusRegister,
)
from schemas.tests_models.seed_models import SeedDevice

__all__ = [
    "ApiErrorDetail",
    "ApiErrorResponse",
    "CacheClearResult",
    "CacheDeleteResult",
    "CacheExistsResult",
    "CacheHealthResponse",
    "CacheKeyEntry",
    "CacheKeysResult",
    "CacheSetResult",
    "DbHealthResponse",
    "DbServerInfo",
    "MockModbusContract",
    "MockModbusDevice",
    "MockModbusRegister",
    "ReadinessChecks",
    "ReadinessResponse",
    "RedisHealthResponse",
    "SeedDevice",
]
