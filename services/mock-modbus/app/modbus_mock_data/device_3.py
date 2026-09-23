"""Mock register data for device-3 — utility-scale PV plant."""
from __future__ import annotations

from app.models import DeviceSpec, RegisterSpec

# The real site's register map defines no FC04 input registers, so
# ``input_registers`` is left to its default empty map.
DEVICE = DeviceSpec(
    unit_id=3,
    name="device_3",
    device_type="pv",
    # Nameplate, consistent with holding register 254 (total AC active power
    # x0.1 kW, capped at 33000 = 3300 kW = 3.3 MW).
    kw_max=3300.0,
    host="0.0.0.0",
    port=5022,
    holding_registers={
        # ── POI Meter (201–237) ─────────────────────────────────────────────────
        201: RegisterSpec(name="poi_active_power_total", type="random", unit="kW", scale=0.1, min=-7500, max=7500),
        203: RegisterSpec(name="poi_reactive_power_total", type="random", unit="kVAR", scale=0.1, min=-5000, max=5000),
        205: RegisterSpec(name="poi_apparent_power_total", type="random", unit="kVA", scale=0.1, min=0, max=9000),
        207: RegisterSpec(name="poi_voltage_avg_ln", type="random", unit="V", scale=0.01, min=25000, max=30000),
        209: RegisterSpec(name="poi_voltage_avg_ll", type="random", unit="V", scale=0.01, min=43000, max=52000),
        211: RegisterSpec(name="poi_current_avg", type="random", unit="A", scale=0.1, min=0, max=12000),
        213: RegisterSpec(name="poi_power_factor", type="random", unit="pu", scale=0.0001, min=-10000, max=10000),
        215: RegisterSpec(name="poi_frequency", type="random", unit="Hz", scale=0.001, min=59500, max=60500),
        217: RegisterSpec(name="poi_voltage_a", type="random", unit="V", scale=0.01, min=25000, max=30000),
        219: RegisterSpec(name="poi_voltage_b", type="random", unit="V", scale=0.01, min=25000, max=30000),
        221: RegisterSpec(name="poi_voltage_c", type="random", unit="V", scale=0.01, min=25000, max=30000),
        223: RegisterSpec(name="poi_current_a", type="random", unit="A", scale=0.1, min=0, max=12000),
        225: RegisterSpec(name="poi_current_b", type="random", unit="A", scale=0.1, min=0, max=12000),
        227: RegisterSpec(name="poi_current_c", type="random", unit="A", scale=0.1, min=0, max=12000),
        229: RegisterSpec(name="poi_active_power_a", type="random", unit="kW", scale=0.1, min=-2500, max=2500),
        231: RegisterSpec(name="poi_active_power_b", type="random", unit="kW", scale=0.1, min=-2500, max=2500),
        233: RegisterSpec(name="poi_active_power_c", type="random", unit="kW", scale=0.1, min=-2500, max=2500),
        235: RegisterSpec(name="poi_import_energy_total", type="random", unit="MWh", scale=1.0, min=0, max=5000),
        237: RegisterSpec(name="poi_export_energy_total", type="random", width=32, unit="MWh", scale=1.0, min=0, max=80000),  # 32-bit: 80000 does not fit a uint16

        # Even addresses 202–236 — gaps (former low words of the 32-bit fields
        # above) — not defined. 238 is the low word of 237, which is the one
        # field kept at its true 32-bit width.

        # ── Weather (239–248) ──────────────────────────────────────────────────
        239: RegisterSpec(name="ghi_irradiance", type="random", unit="W/m²", scale=1.0, min=0, max=1200),
        240: RegisterSpec(name="ghi_sensor_body_temp", type="random", unit="°C", scale=0.1, min=-200, max=800),
        241: RegisterSpec(name="ghi_status_flags", type="random", unit=None, scale=1.0, min=0, max=7),  # bitfield (narrowed from CSV's 0..65535)
        242: RegisterSpec(name="poa1_irradiance", type="random", unit="W/m²", scale=0.1, min=0, max=12000),
        243: RegisterSpec(name="poa1_cell_temp", type="random", unit="°C", scale=0.1, min=-100, max=900),
        244: RegisterSpec(name="poa1_ambient_temp", type="random", unit="°C", scale=0.1, min=-100, max=600),
        245: RegisterSpec(name="poa1_wind_speed", type="random", unit="m/s", scale=0.1, min=0, max=400),
        246: RegisterSpec(name="poa2_irradiance", type="random", unit="W/m²", scale=0.1, min=0, max=12000),
        247: RegisterSpec(name="poa2_cell_temp", type="random", unit="°C", scale=0.1, min=-100, max=900),
        248: RegisterSpec(name="poa2_ambient_temp", type="random", unit="°C", scale=0.1, min=-100, max=600),

        # ── PV Fleet (249–267) ─────────────────────────────────────────────────
        249: RegisterSpec(name="available_inverter_count", type="random", unit=None, scale=1.0, min=0, max=55),
        250: RegisterSpec(name="running_inverter_count", type="random", unit=None, scale=1.0, min=0, max=55),
        251: RegisterSpec(name="faulted_inverter_count", type="random", unit=None, scale=1.0, min=0, max=5),  # narrowed from CSV's 0..55
        252: RegisterSpec(name="standby_inverter_count", type="random", unit=None, scale=1.0, min=0, max=55),
        253: RegisterSpec(name="derated_inverter_count", type="random", unit=None, scale=1.0, min=0, max=8),  # narrowed from CSV's 0..55
        254: RegisterSpec(name="total_ac_active_power", type="random", unit="kW", scale=0.1, min=0, max=33000),
        256: RegisterSpec(name="total_ac_reactive_power", type="random", unit="kVAR", scale=0.1, min=-20000, max=20000),
        258: RegisterSpec(name="total_dc_input_power", type="random", unit="kW", scale=0.1, min=0, max=36000),
        260: RegisterSpec(name="total_daily_energy", type="random", unit="kWh", scale=1.0, min=0, max=30000),
        262: RegisterSpec(name="total_lifetime_energy", type="random", width=32, unit="MWh", scale=1.0, min=0, max=85000),  # 32-bit: 85000 does not fit a uint16
        264: RegisterSpec(name="avg_inverter_efficiency", type="random", unit="%", scale=0.01, min=0, max=10000),
        265: RegisterSpec(name="max_heatsink_temp", type="random", unit="°C", scale=0.1, min=-100, max=1000),
        266: RegisterSpec(name="max_internal_temp", type="random", unit="°C", scale=0.1, min=-100, max=1000),
        267: RegisterSpec(name="alarm_summary_flags", type="random", unit=None, scale=1.0, min=0, max=7),  # bitfield (narrowed from CSV's 0..65535)

        # 255,257,259,261 — gaps (former low words of the 32-bit aggregates above)
        # — not defined. 263 is the low word of 262, kept at its true 32-bit width.

        # ── Inverter 01 (268–275) ──────────────────────────────────────────────
        268: RegisterSpec(name="inv01_mode", type="random", unit=None, scale=1.0, min=1, max=5, enum_values={1: "derate", 2: "running", 3: "standby", 4: "check", 5: "fault"}),  # 1=Derate(0x0800) 2=Running(0x1000) 3=Standby(0x2000) 4=Check(0x4000) 5=Fault(0x8000)
        269: RegisterSpec(name="inv01_ac_active_power", type="random", unit="kW", scale=0.1, min=0, max=700),
        270: RegisterSpec(name="inv01_ac_reactive_power", type="random", unit="kVAR", scale=0.1, min=-700, max=700),
        271: RegisterSpec(name="inv01_grid_voltage_ab", type="random", unit="V", scale=0.1, min=4300, max=5200),
        272: RegisterSpec(name="inv01_grid_current_a", type="random", unit="A", scale=0.1, min=0, max=1000),
        273: RegisterSpec(name="inv01_pv_input_power", type="random", unit="kW", scale=0.1, min=0, max=750),
        274: RegisterSpec(name="inv01_internal_temp", type="random", unit="°C", scale=0.1, min=-100, max=1000),
        275: RegisterSpec(name="inv01_fault_code", type="random", unit=None, scale=1.0, min=0, max=10),  # 0=none, narrowed from CSV's 0..65535

        # ── Inverter 02 (276–283) ──────────────────────────────────────────────
        276: RegisterSpec(name="inv02_mode", type="random", unit=None, scale=1.0, min=1, max=5, enum_values={1: "derate", 2: "running", 3: "standby", 4: "check", 5: "fault"}),
        277: RegisterSpec(name="inv02_ac_active_power", type="random", unit="kW", scale=0.1, min=0, max=700),
        278: RegisterSpec(name="inv02_ac_reactive_power", type="random", unit="kVAR", scale=0.1, min=-700, max=700),
        279: RegisterSpec(name="inv02_grid_voltage_ab", type="random", unit="V", scale=0.1, min=4300, max=5200),
        280: RegisterSpec(name="inv02_grid_current_a", type="random", unit="A", scale=0.1, min=0, max=1000),
        281: RegisterSpec(name="inv02_pv_input_power", type="random", unit="kW", scale=0.1, min=0, max=750),
        282: RegisterSpec(name="inv02_internal_temp", type="random", unit="°C", scale=0.1, min=-100, max=1000),
        283: RegisterSpec(name="inv02_fault_code", type="random", unit=None, scale=1.0, min=0, max=10),

        # ── Inverter 03 (284–291) ──────────────────────────────────────────────
        284: RegisterSpec(name="inv03_mode", type="random", unit=None, scale=1.0, min=1, max=5, enum_values={1: "derate", 2: "running", 3: "standby", 4: "check", 5: "fault"}),
        285: RegisterSpec(name="inv03_ac_active_power", type="random", unit="kW", scale=0.1, min=0, max=700),
        286: RegisterSpec(name="inv03_ac_reactive_power", type="random", unit="kVAR", scale=0.1, min=-700, max=700),
        287: RegisterSpec(name="inv03_grid_voltage_ab", type="random", unit="V", scale=0.1, min=4300, max=5200),
        288: RegisterSpec(name="inv03_grid_current_a", type="random", unit="A", scale=0.1, min=0, max=1000),
        289: RegisterSpec(name="inv03_pv_input_power", type="random", unit="kW", scale=0.1, min=0, max=750),
        290: RegisterSpec(name="inv03_internal_temp", type="random", unit="°C", scale=0.1, min=-100, max=1000),
        291: RegisterSpec(name="inv03_fault_code", type="random", unit=None, scale=1.0, min=0, max=10),

        # ── Inverter 04 (292–299) ──────────────────────────────────────────────
        292: RegisterSpec(name="inv04_mode", type="random", unit=None, scale=1.0, min=1, max=5, enum_values={1: "derate", 2: "running", 3: "standby", 4: "check", 5: "fault"}),
        293: RegisterSpec(name="inv04_ac_active_power", type="random", unit="kW", scale=0.1, min=0, max=700),
        294: RegisterSpec(name="inv04_ac_reactive_power", type="random", unit="kVAR", scale=0.1, min=-700, max=700),
        295: RegisterSpec(name="inv04_grid_voltage_ab", type="random", unit="V", scale=0.1, min=4300, max=5200),
        296: RegisterSpec(name="inv04_grid_current_a", type="random", unit="A", scale=0.1, min=0, max=1000),
        297: RegisterSpec(name="inv04_pv_input_power", type="random", unit="kW", scale=0.1, min=0, max=750),
        298: RegisterSpec(name="inv04_internal_temp", type="random", unit="°C", scale=0.1, min=-100, max=1000),
        299: RegisterSpec(name="inv04_fault_code", type="random", unit=None, scale=1.0, min=0, max=10),
    },
)
