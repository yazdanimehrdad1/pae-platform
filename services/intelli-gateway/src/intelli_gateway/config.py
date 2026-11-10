"""Service configuration (pydantic-settings), read from the environment and this service's .env.

This is the only place configuration is read. The Claude model name lives here and nowhere else.
"""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from intelli_gateway.schemas.users import BOOTSTRAP_ADMIN_EMAIL, DEMO_EMAIL

# services/intelli-gateway/.env, anchored to this file so it loads the same way from any CWD.
# Never a parent directory's .env.
SERVICE_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SERVICE_ENV_FILE, env_file_encoding="utf-8", extra="ignore", populate_by_name=True
    )

    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Claude (all calls go through services/claude/client.py) ---
    # Unset is allowed: the SDK then falls back to other credential sources (e.g. `ant auth login`).
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    claude_model: str = Field(default="claude-opus-5-5", alias="CLAUDE_MODEL")
    claude_effort: Effort = Field(default="high", alias="CLAUDE_EFFORT")
    claude_max_tokens: int = Field(default=16000, gt=0, alias="CLAUDE_MAX_TOKENS")
    # Per-request HTTP timeout to the Claude API, in seconds.
    claude_request_timeout_s: float = Field(default=120.0, gt=0, alias="CLAUDE_REQUEST_TIMEOUT_S")
    # Server-side refusal fallback (`fallbacks: "default"`). Claude API only; not on Bedrock,
    # Vertex or Foundry.
    claude_refusal_fallback: bool = Field(default=True, alias="CLAUDE_REFUSAL_FALLBACK")

    # --- Agent loop ---
    agent_max_iterations: int = Field(default=10, ge=1, alias="AGENT_MAX_ITERATIONS")
    agent_timeout_s: float = Field(default=180.0, gt=0, alias="AGENT_TIMEOUT_S")

    # --- Site knowledge ---
    # Above this many tokens, a warning is logged: the signal to add search/RAG.
    knowledge_token_warn: int = Field(default=150_000, gt=0, alias="KNOWLEDGE_TOKEN_WARN")

    # --- Tool output bounds ---
    tool_max_output_chars: int = Field(default=20_000, gt=0, alias="TOOL_MAX_OUTPUT_CHARS")
    tool_max_rows: int = Field(default=50, gt=0, alias="TOOL_MAX_ROWS")
    tool_history_samples: int = Field(default=12, ge=2, alias="TOOL_HISTORY_SAMPLES")
    tool_history_max_days: int = Field(default=31, gt=0, alias="TOOL_HISTORY_MAX_DAYS")
    # Series site functions: the longest window, and the default resolution's interval (the
    # first reading of each; the AI may ask for every reading instead). Longer periods: a
    # function that computes the answer.
    tool_series_max_hours: int = Field(default=6, gt=0, alias="TOOL_SERIES_MAX_HOURS")
    tool_series_interval_minutes: int = Field(
        default=15, ge=1, le=60, alias="TOOL_SERIES_INTERVAL_MINUTES"
    )
    # A point with no new reading for longer than this is flagged stale (device not reporting).
    data_stale_after_s: float = Field(default=600, gt=0, alias="DATA_STALE_AFTER_S")

    # --- backend-ot (all site data; every call is in services/backend_ot/) ---
    backend_ot_url: str = Field(default="http://localhost:8000", alias="BACKEND_OT_URL")
    backend_ot_timeout_s: float = Field(default=10.0, gt=0, alias="BACKEND_OT_TIMEOUT_S")
    backend_ot_retries: int = Field(default=3, ge=1, alias="BACKEND_OT_RETRIES")
    # How long the device and point catalog of a site is cached.
    backend_ot_catalog_ttl_s: float = Field(default=60, ge=0, alias="BACKEND_OT_CATALOG_TTL_S")

    # --- Site profiles (site_profile/; docs/KNOWLEDGE_PLAN.md) ---
    # The AI always sees only sites a site admin approved, and only their approved devices and
    # points (no setting turns that off).
    # How often backend-ot is read for pending changes (also at startup). 0 disables the job
    # (sync only through POST /api/v1/site-profiles/sync).
    site_profile_sync_interval_minutes: int = Field(
        default=15, ge=0, alias="SITE_PROFILE_SYNC_INTERVAL_MINUTES"
    )
    # How long a site's approved view is cached per instance (an approval here drops it at once).
    site_profile_cache_ttl_s: float = Field(default=30, ge=0, alias="SITE_PROFILE_CACHE_TTL_S")

    # --- Database (this service's own Postgres) ---
    # Required to start: users, site profiles and forecasts live there (startup fails with a
    # ConfigurationError without it). In the dev stack compose sets it.
    database_url: SecretStr | None = Field(default=None, alias="DATABASE_URL")

    # --- Users and login (auth/) ---
    # Dev only: a request without a session cookie is taken from the X-User-Id / X-Roles /
    # X-Site-Ids headers (or the dev user). Off = every /api/v1 route except login needs a session.
    # Off by default (and in the cloud): web-plusdas logs in. Tests and host experiments turn it on.
    auth_dev_headers: bool = Field(default=False, alias="AUTH_DEV_HEADERS")
    # Sliding: each use (written at most once a minute) pushes the expiry this far ahead.
    session_ttl_days: float = Field(default=30, gt=0, alias="SESSION_TTL_DAYS")
    # true once the site is served over HTTPS: the browser then sends the cookie only over HTTPS.
    session_cookie_secure: bool = Field(default=False, alias="SESSION_COOKIE_SECURE")
    # A fresh environment's first admin: created at startup while there are no users at all (the
    # cloud deploy writes the password from Secret Manager). That admin adds the others in the UI.
    bootstrap_admin_email: str = Field(default=BOOTSTRAP_ADMIN_EMAIL, alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: SecretStr | None = Field(
        default=None, alias="BOOTSTRAP_ADMIN_PASSWORD"
    )
    # The demo login (the local stack and the dev cloud; never prod): when set, startup keeps a
    # demo_user_email engineer account with this password. Nobody can change its password from
    # inside it (many people share it).
    demo_user_password: SecretStr | None = Field(default=None, alias="DEMO_USER_PASSWORD")
    demo_user_email: str = Field(default=DEMO_EMAIL, alias="DEMO_USER_EMAIL")

    # --- PV forecast (solar_forecast/; sources in services/<name>/) ---
    forecast_enabled: bool = Field(default=True, alias="FORECAST_ENABLED")
    # A registered source name (solar_forecast/registry.py): open_meteo, noaa_hrrr, fake.
    forecast_source: str = Field(default="open_meteo", alias="FORECAST_SOURCE")
    # Tried in order when the primary fails; comma-separated, empty = no fallback.
    forecast_fallback_sources: Annotated[tuple[str, ...], NoDecode] = Field(
        default=(), alias="FORECAST_FALLBACK_SOURCES"
    )
    forecast_horizon_hours: int = Field(default=72, ge=1, le=384, alias="FORECAST_HORIZON_HOURS")
    forecast_resolution_minutes: Literal[15, 60] = Field(
        default=15, alias="FORECAST_RESOLUTION_MINUTES"
    )
    # The refresh job runs at startup, then every this many minutes. 0 disables the job
    # (refresh only through POST /api/v1/forecast/refresh).
    forecast_fetch_interval_minutes: int = Field(
        default=15, ge=0, alias="FORECAST_FETCH_INTERVAL_MINUTES"
    )
    forecast_retention_days: int = Field(default=7, ge=1, alias="FORECAST_RETENTION_DAYS")

    # Open-Meteo (services/open_meteo/). Hosted free API: non-commercial use only. Point the URL
    # at https://customer-api.open-meteo.com (with a key) or a self-hosted server for production.
    open_meteo_base_url: str = Field(
        default="https://api.open-meteo.com", alias="OPEN_METEO_BASE_URL"
    )
    open_meteo_api_key: SecretStr | None = Field(default=None, alias="OPEN_METEO_API_KEY")
    open_meteo_timeout_s: float = Field(default=15.0, gt=0, alias="OPEN_METEO_TIMEOUT_S")
    open_meteo_retries: int = Field(default=3, ge=1, alias="OPEN_METEO_RETRIES")
    # The free tier allows 600 requests a minute and 10,000 a day.
    open_meteo_max_calls_per_minute: int = Field(
        default=500, ge=1, alias="OPEN_METEO_MAX_CALLS_PER_MINUTE"
    )

    @field_validator("bootstrap_admin_email", "demo_user_email", mode="before")
    @classmethod
    def _default_when_empty(cls, value: object, info: ValidationInfo) -> object:
        # The cloud compose passes these from config/<env>.env; one left out arrives empty.
        if isinstance(value, str) and not value.strip():
            return cls.model_fields[info.field_name or ""].default
        return value

    @field_validator("forecast_fallback_sources", mode="before")
    @classmethod
    def _split_sources(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(name.strip() for name in value.split(",") if name.strip())
        return value


def load_settings() -> Settings:
    return Settings()
