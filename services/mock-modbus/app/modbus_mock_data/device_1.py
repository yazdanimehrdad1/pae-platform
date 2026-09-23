"""Mock register data for device-1 — 3-phase grid-tied solar inverter."""
from __future__ import annotations

from app.models import DeviceSpec, RegisterSpec

DEVICE = DeviceSpec(
    unit_id=1,
    name="device_1",
    device_type="pv",
    # Nameplate, consistent with holding register 4 (active power W, capped
    # at 2900 W = 2.9 kW).
    kw_max=3.0,
    host="0.0.0.0",
    port=5020,
    holding_registers={
        # ── INT16 measurements (1–11) ──────────────────────────────────────
        1: RegisterSpec(name="dc_bus_voltage", type="random", unit="V", scale=0.1, min=0, max=4),
        2: RegisterSpec(name="pv_array_voltage", type="profile_static", unit="V", scale=0.1, min=3000, max=4800),
        3: RegisterSpec(name="grid_frequency", type="random", unit="Hz", scale=0.01, min=4990, max=5010),  # grid-side, not sun-driven
        4: RegisterSpec(name="active_power", type="profile_static", unit="W", scale=1.0, min=1000, max=2900),  # from pv_profile_static.py, address 4
        5: RegisterSpec(name="inverter_temperature", type="profile_static", unit="°C", scale=0.1, min=200, max=750),
        6: RegisterSpec(name="pv_string_current", type="profile_static", unit="A", scale=0.1, min=50, max=180),
        7: RegisterSpec(name="ac_output_current", type="profile_static", unit="A", scale=0.1, min=11, max=45),
        8: RegisterSpec(name="power_factor", type="profile_static", unit=None, scale=0.001, min=850, max=999),
        9: RegisterSpec(name="active_fault_code", type="random", unit=None, scale=1.0, min=0, max=10),  # 0 = none, 1–10 = fault — discrete code, never curve it
        10: RegisterSpec(name="apparent_power", type="profile_static", unit="VA", scale=1.0, min=5200, max=6500),
        11: RegisterSpec(name="total_runtime_hours", type="random", unit=None, scale=1.0, min=8100, max=9500),  # ~1 yr baseline — monotonic counter, never curve it

        # ── Enum registers (16–21) — valid range 1–N ────────────────────────
        16: RegisterSpec(name="inverter_state", type="random", unit=None, scale=1.0, min=1, max=6, enum_values={1: "off", 2: "startup", 3: "mppt", 4: "derating", 5: "fault", 6: "night"}),
        17: RegisterSpec(name="grid_connection_state", type="random", unit=None, scale=1.0, min=1, max=4, enum_values={1: "disconnected", 2: "connecting", 3: "connected", 4: "fault"}),
        18: RegisterSpec(name="alarm_severity", type="random", unit=None, scale=1.0, min=1, max=5, enum_values={1: "none", 2: "info", 3: "warning", 4: "minor", 5: "major"}),
        19: RegisterSpec(name="string_configuration", type="random", unit=None, scale=1.0, min=1, max=4, enum_values={1: "single_string", 2: "dual", 3: "triple", 4: "quad"}),
        20: RegisterSpec(name="system_state", type="random", unit=None, scale=1.0, min=1, max=4, enum_values={1: "init", 2: "running", 3: "degraded", 4: "offline"}),
        21: RegisterSpec(name="cooling_fan_level", type="random", unit=None, scale=1.0, min=1, max=5, enum_values={1: "off", 2: "low", 3: "medium", 4: "high", 5: "max"}),

        # ── Bitfield registers (22–31) — each bit is an independent flag ────
        22: RegisterSpec(name="alarm_flags", type="random", unit=None, scale=1.0, min=0, max=255),  # bits 0–7: alarm types (overcurrent, overvoltage, overtemp, …)
        23: RegisterSpec(name="warning_flags", type="random", unit=None, scale=1.0, min=0, max=255),  # bits 0–7: warning types (high temp, low irradiance, grid fluctuation, …)
        24: RegisterSpec(name="grid_fault_flags", type="random", unit=None, scale=1.0, min=0, max=63, bit_flags={0: "overvoltage", 1: "undervoltage", 2: "overfreq", 3: "underfreq", 4: "phase_loss", 5: "imbalance"}),
        25: RegisterSpec(name="inverter_fault_flags", type="random", unit=None, scale=1.0, min=0, max=63, bit_flags={0: "overtemp", 1: "dc_overv", 2: "dc_underv", 3: "overcurrent", 4: "short", 5: "insulation"}),
        26: RegisterSpec(name="feature_enable_flags", type="random", unit=None, scale=1.0, min=0, max=63, bit_flags={0: "mppt", 1: "anti_island", 2: "react_pwr_ctrl", 3: "pwr_limit", 4: "remote_stop", 5: "logging"}),
        27: RegisterSpec(name="digital_input_flags", type="random", unit=None, scale=1.0, min=0, max=31, bit_flags={0: "e_stop", 1: "door", 2: "ac_switch", 3: "dc_switch", 4: "gfi_relay"}),
        28: RegisterSpec(name="digital_output_flags", type="random", unit=None, scale=1.0, min=0, max=31, bit_flags={0: "fan", 1: "fault_relay", 2: "ac_contactor", 3: "dc_contactor", 4: "buzzer"}),
        29: RegisterSpec(name="pv_string_health_flags", type="random", unit=None, scale=1.0, min=0, max=255, bit_flags={0: "string_0", 1: "string_1", 2: "string_2", 3: "string_3", 4: "string_4", 5: "string_5", 6: "string_6", 7: "string_7"}),
        30: RegisterSpec(name="comms_status_flags", type="random", unit=None, scale=1.0, min=0, max=63, bit_flags={0: "modbus", 1: "can", 2: "ethernet", 3: "wifi", 4: "bt", 5: "rs485"}),
        31: RegisterSpec(name="hardware_health_flags", type="random", unit=None, scale=1.0, min=0, max=63, bit_flags={0: "psu", 1: "igbt", 2: "caps", 3: "heatsink", 4: "sensors", 5: "firmware"}),
    },
    input_registers={
        # ── INT16 per-phase & environmental measurements (1001–1011) ────────────
        1001: RegisterSpec(name="ac_voltage_l1_n", type="random", unit="V", scale=0.1, min=2270, max=2430),  # grid-side; L1/L2/L3 bands overlap by design
        1002: RegisterSpec(name="ac_voltage_l2_n", type="random", unit="V", scale=0.1, min=2268, max=2428),  # grid-side
        1003: RegisterSpec(name="ac_voltage_l3_n", type="random", unit="V", scale=0.1, min=2272, max=2432),  # grid-side
        1004: RegisterSpec(name="ac_current_l1", type="profile_static", unit="A", scale=0.1, min=10, max=80),
        1005: RegisterSpec(name="ac_current_l2", type="profile_static", unit="A", scale=0.1, min=10, max=80),
        1006: RegisterSpec(name="ac_current_l3", type="profile_static", unit="A", scale=0.1, min=10, max=80),
        1007: RegisterSpec(name="solar_irradiance", type="profile_static", unit="W/m²", scale=1.0, min=100, max=1100),  # from pv_profile_static.py, address 1007
        1008: RegisterSpec(name="ambient_temperature", type="profile_static", unit="°C", scale=0.1, min=100, max=450),  # static; peaks 15:00, air lags the sun
        1009: RegisterSpec(name="module_temperature", type="profile_static", unit="°C", scale=0.1, min=200, max=650),  # static; blended from irradiance + ambient
        1010: RegisterSpec(name="daily_energy_generated", type="random", unit="Wh", scale=0.1, min=0, max=500),  # cumulative counter, never curve it
        1011: RegisterSpec(name="lifetime_energy", type="random", unit="kWh", scale=0.01, min=1000, max=9999),  # cumulative counter, never curve it

        # ── Enum registers (1016–1021) — valid range 1–N ────────────────────────
        1016: RegisterSpec(name="mppt_algorithm", type="random", unit=None, scale=1.0, min=1, max=4, enum_values={1: "fixed", 2: "perturb_observe", 3: "incrementalconductance", 4: "ripplecorrelation"}),
        1017: RegisterSpec(name="phase_rotation", type="random", unit=None, scale=1.0, min=1, max=3, enum_values={1: "abc", 2: "acb", 3: "unknown"}),
        1018: RegisterSpec(name="anti_islanding_mode", type="random", unit=None, scale=1.0, min=1, max=5, enum_values={1: "off", 2: "passive", 3: "active_low", 4: "active_high", 5: "emergency"}),
        1019: RegisterSpec(name="insulation_status", type="random", unit=None, scale=1.0, min=1, max=4, enum_values={1: "ok", 2: "low", 3: "critical", 4: "fault"}),
        1020: RegisterSpec(name="firmware_update_state", type="random", unit=None, scale=1.0, min=1, max=5, enum_values={1: "idle", 2: "downloading", 3: "verifying", 4: "installing", 5: "rebooting"}),
        1021: RegisterSpec(name="comms_activity_state", type="random", unit=None, scale=1.0, min=1, max=4, enum_values={1: "idle", 2: "active", 3: "busy", 4: "error"}),

        # ── Bitfield registers (1022–1031) — each bit is an independent flag ────
        1022: RegisterSpec(name="phase_over_under_flags", type="random", unit=None, scale=1.0, min=0, max=63, bit_flags={0: "l1_ov", 1: "l1_uv", 2: "l2_ov", 3: "l2_uv", 4: "l3_ov", 5: "l3_uv"}),
        1023: RegisterSpec(name="protection_trip_flags", type="random", unit=None, scale=1.0, min=0, max=255, bit_flags={0: "ocp", 1: "ovp", 2: "uvp", 3: "ofp", 4: "ufp", 5: "otp", 6: "gfci", 7: "rcd"}),  
        1024: RegisterSpec(name="mppt_tracker_active_flags", type="random", unit=None, scale=1.0, min=0, max=255, bit_flags={0: "tracker_0", 1: "tracker_1", 2: "tracker_2", 3: "tracker_3", 4: "tracker_4", 5: "tracker_5", 6: "tracker_6", 7: "tracker_7"}),
        1025: RegisterSpec(name="string_input_presence_flags", type="random", unit=None, scale=1.0, min=0, max=255, bit_flags={0: "string_0", 1: "string_1", 2: "string_2", 3: "string_3", 4: "string_4", 5: "string_5", 6: "string_6", 7: "string_7"}),
        1026: RegisterSpec(name="phase_sync_flags", type="random", unit=None, scale=1.0, min=0, max=63, bit_flags={0: "l1_locked", 1: "l2_locked", 2: "l3_locked", 3: "freq_ok", 4: "angle_ok", 5: "ready"}),
        1027: RegisterSpec(name="calibration_done_flags", type="random", unit=None, scale=1.0, min=0, max=63, bit_flags={0: "v_sensor", 1: "i_sensor", 2: "temp", 3: "irr", 4: "freq", 5: "energy"}),
        1028: RegisterSpec(name="self_test_result_flags", type="random", unit=None, scale=1.0, min=0, max=255, bit_flags={0: "subsystem_0", 1: "subsystem_1", 2: "subsystem_2", 3: "subsystem_3", 4: "subsystem_4", 5: "subsystem_5", 6: "subsystem_6", 7: "subsystem_7"}),  # bit SET = passed, inverted vs the fault/alarm registers
        1029: RegisterSpec(name="external_sensor_presence_flags", type="random", unit=None, scale=1.0, min=0, max=63, bit_flags={0: "pyranometer", 1: "wind", 2: "rain", 3: "amb_temp", 4: "mod_temp", 5: "grid_meter"}),
        1030: RegisterSpec(name="network_link_flags", type="random", unit=None, scale=1.0, min=0, max=31, bit_flags={0: "modbus_tcp", 1: "mqtt", 2: "http", 3: "snmp", 4: "dnp3"}),
        1031: RegisterSpec(name="pending_notification_flags", type="random", unit=None, scale=1.0, min=0, max=15, bit_flags={0: "event_log_full", 1: "fw_update_avail", 2: "service_due", 3: "cert_expiry"}),

       
    },
)