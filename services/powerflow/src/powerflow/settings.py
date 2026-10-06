"""Service settings (pydantic-settings), read from the environment and this service's .env.

The site itself (grid, assets, active site) is NOT configured here: it lives in the database
(the only store for sites) and is edited through the API. PROFILES_DIR holds the profile scenario
CSVs; POINT_STANDARD_DIR the PAE point standard CSVs (the Modbus register layout).
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# services/powerflow/, anchored to this file so it resolves the same way from any CWD
# (/app in the container).
SERVICE_ROOT = Path(__file__).resolve().parents[2]
# services/powerflow/.env. Never a parent directory's .env.
SERVICE_ENV_FILE = SERVICE_ROOT / ".env"
DEFAULT_PROFILES_DIR = Path("profiles")
# The PAE point standard: the Modbus server's register layout comes from these CSVs.
DEFAULT_POINT_STANDARD_DIR = Path("docs/point-standard")
# Modbus server defaults (published in contracts/modbus/powerflow.registers.json).
DEFAULT_MODBUS_PORT = 502
DEFAULT_MODBUS_UNIT_ID = 1
# Host runs (`make run`) against the standalone compose Postgres on its published port.
DEFAULT_DATABASE_URL = "postgresql+asyncpg://powerflow:powerflow@localhost:5436/powerflow"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=SERVICE_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(default=DEFAULT_DATABASE_URL, alias="DATABASE_URL")
    # Profile scenario CSVs (load/, pv/). Relative = relative to the service root.
    profiles_dir: Path = Field(default=DEFAULT_PROFILES_DIR, alias="PROFILES_DIR")
    # Site to load at startup instead of the database's active site (optional).
    active_site: str | None = Field(default=None, alias="ACTIVE_SITE")
    point_standard_dir: Path = Field(default=DEFAULT_POINT_STANDARD_DIR, alias="POINT_STANDARD_DIR")
    # Modbus TCP server (when the site enables interfaces.modbus): one aggregator device.
    modbus_host: str = Field(default="0.0.0.0", alias="MODBUS_HOST")
    modbus_port: int = Field(default=DEFAULT_MODBUS_PORT, ge=0, le=65535, alias="MODBUS_PORT")
    modbus_unit_id: int = Field(
        default=DEFAULT_MODBUS_UNIT_ID, ge=1, le=247, alias="MODBUS_UNIT_ID"
    )

    def resolved_profiles_dir(self) -> Path:
        return _resolve(self.profiles_dir)

    def resolved_point_standard_dir(self) -> Path:
        return _resolve(self.point_standard_dir)


def _resolve(path: Path) -> Path:
    """Relative paths are relative to the service root."""
    return path if path.is_absolute() else SERVICE_ROOT / path


settings = Settings()
