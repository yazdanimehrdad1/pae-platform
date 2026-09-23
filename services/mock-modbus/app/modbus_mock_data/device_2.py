"""Mock register data for device-2 — battery energy storage system (BESS)."""
from __future__ import annotations

from app.models import DeviceSpec, RegisterSpec

DEVICE = DeviceSpec(
    unit_id=2,
    name="device_2",
    device_type="bess",
    # Nameplate, consistent with holding register 105 (inverter output power W,
    # capped at 10000 W = 10 kW).
    kw_max=10.0,
    host="0.0.0.0",
    port=5021,
    holding_registers={
        # ── INT16 measurements (101–105) ──────────────────────────────────────
        101: RegisterSpec(name="pack_voltage", type="random", unit="V", scale=0.1, min=3800, max=5600),
        102: RegisterSpec(name="charge_discharge_current", type="random", unit="A", scale=0.1, min=0, max=1500),
        103: RegisterSpec(name="pack_temperature", type="random", unit="°C", scale=0.1, min=150, max=600),
        104: RegisterSpec(name="state_of_charge", type="random", unit="%", scale=0.1, min=0, max=1000),
        105: RegisterSpec(name="inverter_output_power", type="random", unit="W", scale=1.0, min=0, max=10000),

        # ── Enum registers (110–112) — valid range 1–N ────────────────────────
        110: RegisterSpec(name="battery_state", type="random", unit=None, scale=1.0, min=1, max=5, enum_values={1: "standby", 2: "charging", 3: "discharging", 4: "balancing", 5: "fault"}),
        111: RegisterSpec(name="charge_mode", type="random", unit=None, scale=1.0, min=1, max=4, enum_values={1: "cc", 2: "cv", 3: "cc_cv", 4: "solar_mppt"}),
        112: RegisterSpec(name="grid_interaction_mode", type="random", unit=None, scale=1.0, min=1, max=3, enum_values={1: "island", 2: "grid_follow", 3: "grid_form"}),

        # ── Bitfield registers (113–115) — each bit is an independent flag ────
        113: RegisterSpec(name="cell_group_health_flags", type="random", unit=None, scale=1.0, min=0, max=255, bit_flags={0: "group_0", 1: "group_1", 2: "group_2", 3: "group_3", 4: "group_4", 5: "group_5", 6: "group_6", 7: "group_7"}),
        114: RegisterSpec(name="protection_trigger_flags", type="random", unit=None, scale=1.0, min=0, max=255, bit_flags={0: "ovp", 1: "uvp", 2: "ocp", 3: "otp", 4: "short", 5: "leakage", 6: "bms_fault", 7: "balance_active"}),
        115: RegisterSpec(name="system_control_flags", type="random", unit=None, scale=1.0, min=0, max=31, bit_flags={0: "grid_connected", 1: "ac_relay", 2: "dc_contactor", 3: "precharge", 4: "remote_shutdown"}),

        # ── UINT32 lifetime counters (116–123) ────────────────────────────────
        # Each spans TWO addresses — high word at the address below, low word at
        # address+1 — so the low halves (117, 119, 121, 123) are deliberately
        # not declared. These are the quantities that genuinely overflow a
        # uint16: a 10 kW pack passes 65535 Wh in under seven hours.
        116: RegisterSpec(name="lifetime_energy_charged", type="random", width=32, unit="Wh", scale=1.0, min=0, max=500_000_000),  # ~500 MWh, a decade of cycling
        118: RegisterSpec(name="lifetime_energy_discharged", type="random", width=32, unit="Wh", scale=1.0, min=0, max=450_000_000),  # below charged — round-trip losses
        120: RegisterSpec(name="bms_uptime_seconds", type="random", width=32, unit="s", scale=1.0, min=0, max=315_360_000),  # 10 years; a counter, never curve it
        122: RegisterSpec(name="last_fault_timestamp", type="random", width=32, unit="s", scale=1.0, min=1_700_000_000, max=1_800_000_000),  # unix epoch seconds, ~2023–2027
    },
    input_registers={
        # ── INT16 cell-level & energy measurements (1101–1105) ──────────────────
        1101: RegisterSpec(name="cell_voltage_min", type="random", unit="mV", scale=1.0, min=2800, max=4200),  # min/max/avg share a band by design
        1102: RegisterSpec(name="cell_voltage_max", type="random", unit="mV", scale=1.0, min=2800, max=4200),
        1103: RegisterSpec(name="cell_voltage_avg", type="random", unit="mV", scale=1.0, min=2800, max=4200),
        1104: RegisterSpec(name="total_charge_today", type="random", unit="Wh", scale=0.1, min=0, max=5000),
        1105: RegisterSpec(name="total_discharge_today", type="random", unit="Wh", scale=0.1, min=0, max=5000),

        # 1106–1109 not defined — absent from register map.

        # ── Enum registers (1110–1112) — valid range 1–N ────────────────────────
        1110: RegisterSpec(name="bms_state", type="random", unit=None, scale=1.0, min=1, max=6, enum_values={1: "init", 2: "idle", 3: "charging", 4: "discharging", 5: "balancing", 6: "fault"}),
        1111: RegisterSpec(name="cell_chemistry", type="random", unit=None, scale=1.0, min=1, max=4, enum_values={1: "lfp", 2: "nmc", 3: "nca", 4: "lto"}),
        1112: RegisterSpec(name="thermal_status", type="random", unit=None, scale=1.0, min=1, max=4, enum_values={1: "normal", 2: "warm", 3: "hot", 4: "critical"}),

        # ── Bitfield registers (1113–1115) — each bit is an independent flag ────
        1113: RegisterSpec(name="cell_balancing_flags", type="random", unit=None, scale=1.0, min=0, max=255, bit_flags={0: "group_0", 1: "group_1", 2: "group_2", 3: "group_3", 4: "group_4", 5: "group_5", 6: "group_6", 7: "group_7"}),
        1114: RegisterSpec(name="alarm_status_flags", type="random", unit=None, scale=1.0, min=0, max=255, bit_flags={0: "overtemp", 1: "undertemp", 2: "cell_ov", 3: "cell_uv", 4: "soc_low", 5: "soc_high", 6: "i_high", 7: "bms_err"}),
        1115: RegisterSpec(name="diagnostic_flags", type="random", unit=None, scale=1.0, min=0, max=15, bit_flags={0: "cell_drift", 1: "capacity_fade", 2: "high_resistance", 3: "aging_alert"}),

    },
)
