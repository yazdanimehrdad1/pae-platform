from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# services/mock-modbus/.env — anchored to this file so it loads the same way from any CWD.
# Never a parent directory's .env. Real environment variables take precedence over it.
SERVICE_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    # Enable aggregator mode: all devices on one shared host/port, addressed by unit_id
    aggregator_enabled: bool = True
    modbus_host: str = "0.0.0.0"
    modbus_port: int = 502

    # Enable per-device mode: each device gets its own TCP server (host/port from device file)
    per_device_enabled: bool = False

    # Value returned for any address not present in a device's register map.
    # Matches the docker-compose default (DEFAULT_REGISTER_VALUE=0).
    default_register_value: int = 0
    log_level: str = "INFO"
    random_seed: int | None = None
    # False (default): 1-based addressing — standard Modbus (Modbus Poll, most PLCs)
    # True: 0-based addressing — use when clients send raw PDU addresses (e.g. pymodbus client)
    zero_mode: bool = False

    # ── Profile registers (type="profile_static") ─────────────────────────────
    # These only pick which row of the frozen table a read lands on; the values
    # themselves are literals in app/timeseries_data/pv_profile_static.py.
    # Offset applied on top of UTC to decide where "solar noon" falls. A plain
    # offset rather than a named IANA zone: zoneinfo needs the tzdata package on
    # Windows. No DST — a simulator does not need one.
    profile_timezone_offset_hours: float = Field(default=0.0, gt=-24.0, lt=24.0)
    # How many real minutes one simulated day takes. 1440 = real time; set it
    # low (e.g. 5) to watch a full diurnal cycle without waiting for noon.
    profile_day_minutes: float = Field(default=1440.0, gt=0.0)

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=SERVICE_ENV_FILE,
        env_file_encoding="utf-8",
        # A .env may carry compose-interpolation keys (e.g. MOCK_MODBUS_PORT) that aren't settings.
        extra="ignore",
    )

    @field_validator("random_seed", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v: object) -> object:
        if v == "":
            return None
        return v
