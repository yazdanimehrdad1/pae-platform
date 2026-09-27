"""Service settings (pydantic-settings), read from the environment and this service's .env.

The site itself (grid, assets, Modbus maps, active site) is NOT configured here: it lives in the
database and is edited through the API. SITE_CONFIG_DIR holds the shipped defaults (seeded into
an empty database) and the profile scenario CSVs.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# services/powerflow/, anchored to this file so it resolves the same way from any CWD
# (/app in the container).
SERVICE_ROOT = Path(__file__).resolve().parents[2]
# services/powerflow/.env. Never a parent directory's .env.
SERVICE_ENV_FILE = SERVICE_ROOT / ".env"
DEFAULT_SITE_CONFIG_DIR = Path("site_config")
# Host runs (`make run`) against the standalone compose Postgres on its published port.
DEFAULT_DATABASE_URL = "postgresql+asyncpg://powerflow:powerflow@localhost:5436/powerflow"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SERVICE_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(default=DEFAULT_DATABASE_URL, alias="DATABASE_URL")
    # Default sites/maps (seed) and profile CSVs. Relative = relative to the service root.
    site_config_dir: Path = Field(default=DEFAULT_SITE_CONFIG_DIR, alias="SITE_CONFIG_DIR")
    # Site to load at startup instead of the database's active site (optional).
    active_site: str | None = Field(default=None, alias="ACTIVE_SITE")

    def resolved_site_config_dir(self) -> Path:
        if self.site_config_dir.is_absolute():
            return self.site_config_dir
        return SERVICE_ROOT / self.site_config_dir


settings = Settings()
