"""
Application configuration using Pydantic Settings.

Environment-driven configuration with validation and type safety.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Deployment environments carry vars this service doesn't consume
        # (e.g. legacy MAIN_SEL_751_POLL_*); don't fail startup on them.
        extra="ignore",
    )

    # Modbus Configuration
    modbus_host: str = Field(default="localhost", alias="AGGREGATOR_MODBUS_HOST")
    modbus_port: int = Field(default=502, alias="AGGREGATOR_MODBUS_PORT")
    modbus_device_id: int = Field(default=1, alias="AGGREGATOR_SERVER_ID")
    modbus_timeout_s: float = Field(default=5.0, alias="MODBUS_TIMEOUT_S")
    modbus_retries: int = Field(default=3, alias="MODBUS_RETRIES")

    # Server Configuration
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Redis Configuration
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: str | None = Field(default=None, alias="REDIS_PASSWORD")
    redis_socket_timeout: float = Field(default=5.0, alias="REDIS_SOCKET_TIMEOUT")
    redis_socket_connect_timeout: float = Field(default=5.0, alias="REDIS_SOCKET_CONNECT_TIMEOUT")
    redis_max_connections: int = Field(default=50, alias="REDIS_MAX_CONNECTIONS")
    redis_decode_responses: bool = Field(default=True, alias="REDIS_DECODE_RESPONSES")
    redis_health_check_interval: int = Field(default=30, alias="REDIS_HEALTH_CHECK_INTERVAL")

    # Cache Configuration
    cache_default_ttl: int = Field(default=3600, alias="CACHE_DEFAULT_TTL")  # 1 hour default
    cache_key_prefix: str = Field(default="pae_backend_ot", alias="CACHE_KEY_PREFIX")

    # Database Configuration
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="pae_backend_ot", alias="POSTGRES_DB")
    postgres_user: str = Field(default="pae_backend_ot_user", alias="POSTGRES_USER")
    # Secret: no default on purpose — a missing POSTGRES_PASSWORD must fail loudly at
    # startup rather than silently connect with a known-bad value. Supplied via .env
    # locally and a k8s Secret (from GCP Secret Manager) in the cluster.
    postgres_password: str = Field(alias="POSTGRES_PASSWORD")
    database_pool_size: int = Field(default=10, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, alias="DATABASE_MAX_OVERFLOW")

    @property
    def database_url(self) -> str:
        """Build PostgreSQL connection URL."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # Scheduler Configuration
    scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
    scheduler_leader_lock_ttl: int = Field(default=30, alias="SCHEDULER_LEADER_LOCK_TTL")
    scheduler_heartbeat_interval: int = Field(default=10, alias="SCHEDULER_HEARTBEAT_INTERVAL")
    scheduler_job_lock_ttl: int = Field(default=300, alias="SCHEDULER_JOB_LOCK_TTL")
    scheduler_leader_retry_interval: int = Field(default=5, alias="SCHEDULER_LEADER_RETRY_INTERVAL")

    # Polling Job Configuration
    poll_interval_seconds: int = Field(default=10, alias="POLL_INTERVAL_SECONDS")

    # Pod identification (for Kubernetes)
    pod_name: str = Field(default="", alias="POD_NAME")  # Falls back to HOSTNAME if not set


# Global settings instance
settings = Settings()

