"""Service configuration (pydantic-settings), read from the environment and this service's .env.

This is the only place configuration is read. The Claude model name lives here and nowhere else.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    # A point with no new reading for longer than this is flagged stale (device not reporting).
    data_stale_after_s: float = Field(default=600, gt=0, alias="DATA_STALE_AFTER_S")

    # --- Connectors ---
    # Fake in-memory data only for now; the backend-ot and Postgres connectors come next.
    use_fake_data: bool = Field(default=True, alias="USE_FAKE_DATA")
    backend_ot_url: str = Field(default="http://localhost:8000", alias="BACKEND_OT_URL")
    # Example external API (an Open-Meteo-compatible forecast endpoint). Unset: the
    # get_weather_forecast tool is not registered.
    external_api_url: str | None = Field(default=None, alias="EXTERNAL_API_URL")
    external_api_timeout_s: float = Field(default=10.0, gt=0, alias="EXTERNAL_API_TIMEOUT_S")
    external_api_retries: int = Field(default=3, ge=1, alias="EXTERNAL_API_RETRIES")


def load_settings() -> Settings:
    return Settings()
