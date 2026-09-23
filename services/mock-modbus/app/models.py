"""Pydantic models for mock-device configuration.

Device modules under ``app/modbus_mock_data`` each export a fully-built
:class:`DeviceSpec` whose register maps are ``dict[int, RegisterSpec]`` (see
``app/modbus_mock_data/__init__.py``), so a malformed register map raises at
import time instead of producing bad reads at runtime.

Two fields decide how a register behaves on read:

* :attr:`RegisterSpec.type` — ``"random"`` (default) draws uniformly across
  ``[min, max]`` on every read; ``"profile_static"`` reads a frozen table of
  literal values keyed by register address.
* :attr:`DeviceSpec.device_type` — selects *which* frozen table this device's
  static registers read from.

``type`` defaults to ``"random"``, so a register that says nothing behaves
exactly as it always has.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    StringConstraints,
    model_validator,
)

#: A zero-padded ``HH:MM`` time of day, ``"00:00"`` through ``"23:59"``. The
#: pattern is what rejects ``"13:0"``, ``"25:00"`` and ``"13:99"`` at import.
SlotKey = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]

#: A Modbus register address — 16-bit, so 0 through 65535.
RegisterAddress = Annotated[int, Field(ge=0, le=0xFFFF)]

#: A raw register value. The lower bound allows signed (int16) quantities to be
#: written naturally; the read path wraps them to two's-complement uint16.
RegisterValue = Annotated[int, Field(ge=-0x8000, le=0xFFFF)]

#: A bit position within a 16-bit register.
BitPosition = Annotated[int, Field(ge=0, le=15)]


class StaticProfile(BaseModel):
    """A frozen day of register values, backing ``type="profile_static"``.

    See ``app/timeseries_data/pv_profile_static.py`` for the real table, and
    ``MockRegisterBlock`` for the lookup.
    """

    model_config = ConfigDict(extra="forbid")

    interval_minutes: PositiveInt = 5
    rows: dict[SlotKey, dict[RegisterAddress, RegisterValue]]


class DeviceType(str, Enum):
    """Kind of equipment a device emulates.

    Selects which frozen profile table a device's ``type="profile_static"``
    registers read from (see ``app.server._static_profile_for``). A ``str`` enum
    so device modules can write ``device_type="pv"`` as a plain string; pydantic
    coerces it and raises on a typo at import.
    """

    #: Photovoltaic generation — a single inverter or a whole plant.
    PV = "pv"
    #: Battery energy storage.
    BESS = "bess"
    #: Intelligent Electronic Device — meter, relay, controller.
    IED = "ied"


class RegisterSpec(BaseModel):
    """How one Modbus register produces its value.

    ``min``/``max`` are the inclusive bounds every read stays within.
    """

    model_config = ConfigDict(extra="forbid")

    #: What this register represents, as a snake_case identifier — safe to use as
    #: a dict key, CSV column or metric label. Required: a register that cannot
    #: say what it is is not much use to a client. The unit, scale and
    #: engineering range stay in the trailing comment, which is genuinely
    #: different information from the name.
    name: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    #: How the value is produced on each read:
    #:
    #: * ``"random"`` — uniform draw across ``[min, max]``.
    #: * ``"profile_static"`` — looked up in a frozen table of literal values
    #:   keyed by this register's *address*
    #:   (``app/timeseries_data/pv_profile_static.py``).
    #:
    #: Shadows the builtin ``type`` inside the class body; harmless for pydantic
    #: and kept because it reads naturally at the call sites.
    type: Literal["random", "profile_static"] = "random"
    #: Register width in bits. Modbus has no 32-bit register: a ``width=32``
    #: value occupies **two consecutive addresses** — high word at its own
    #: address, low word at ``address + 1``. The low address must not be
    #: declared separately (``RegisterValues`` rejects that at startup).
    width: Literal[16, 32] = 16
    #: Engineering unit of the decoded value, or ``None`` for dimensionless and
    #: coded registers (power factor, enums, bitfields, counts).
    unit: Optional[str] = None
    #: Multiply a raw register value by this to get engineering units:
    #: ``7600`` with ``scale=0.1`` is 760.0 V. This is the Modbus convention;
    #: note it is the reciprocal of the "×10" form the old comments used.
    scale: float = Field(default=1.0, gt=0)
    min: int
    max: int
    #: Enum registers: raw value -> what it means.
    enum_values: Optional[dict[RegisterValue, str]] = None
    #: Bitfield registers: bit position -> what that bit means.
    bit_flags: Optional[dict[BitPosition, str]] = None

    @model_validator(mode="after")
    def _check_bounds(self) -> "RegisterSpec":
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) must be <= max ({self.max})")
        if self.enum_values and self.bit_flags:
            raise ValueError(
                f"{self.name}: a register is either an enum or a bitfield, not both"
            )
        # The band must survive the wire. Without this a max of 80000 on a
        # 16-bit register silently wraps to 14464 on every read.
        floor, ceiling = (-0x8000, 0xFFFF) if self.width == 16 else (-0x8000_0000, 0xFFFF_FFFF)
        if not (floor <= self.min and self.max <= ceiling):
            raise ValueError(
                f"{self.name}: [{self.min}, {self.max}] does not fit a {self.width}-bit "
                f"register (allowed {floor}..{ceiling}) — use width=32 if the point is "
                "genuinely 32-bit"
            )
        if self.width == 32 and self.type == "profile_static":
            raise ValueError(
                f"{self.name}: profile_static tables hold 16-bit values, so they "
                "cannot back a 32-bit register"
            )
        return self


class DeviceSpec(BaseModel):
    """A single mock Modbus device discovered from a device module."""

    model_config = ConfigDict(extra="forbid")

    unit_id: int
    name: str
    #: Required on purpose: a device module that forgets it should fail loudly
    #: at import rather than silently serving a flat curve.
    device_type: DeviceType
    host: str
    port: int
    #: Nameplate rating in kW. Optional because an ``ied`` (meter, relay) has no
    #: nameplate, but required by the timeseries generators in
    #: ``app/timeseries_data`` — they scale a whole day's output from it.
    kw_max: Optional[float] = Field(default=None, gt=0)
    holding_registers: dict[int, RegisterSpec] = Field(default_factory=dict)
    input_registers: dict[int, RegisterSpec] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_register_names_unique(self) -> "DeviceSpec":
        """Register names must be unique across BOTH maps on a device.

        They are identifiers — a duplicate would make "read me `active_power`"
        ambiguous, which defeats the point of naming them at all.
        """
        seen: dict[str, int] = {}
        for register_map in (self.holding_registers, self.input_registers):
            for address, spec in register_map.items():
                if spec.name in seen:
                    raise ValueError(
                        f"duplicate register name {spec.name!r} on {self.name}: "
                        f"addresses {seen[spec.name]} and {address}"
                    )
                seen[spec.name] = address
        return self
