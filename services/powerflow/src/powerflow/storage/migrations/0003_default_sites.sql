-- The default sites, inserted once by this migration: the database is the only store for
-- sites (there are no seed files). A site's config is its full SiteConfig JSON (every field
-- explicit), between $site$ quotes. Changing a default site later means a new migration (or an
-- API edit), never editing this file: applied migrations don't run again.
--
-- ON CONFLICT DO UPDATE: a database seeded from the old JSON files is brought up to date once.
-- storage/seed_data.py reads this file for tests and the Postman example.
-- The site names were changed before release; 0004 renames them in a database that ran the
-- earlier version of this file, and adds each site's category (these are 'default').

INSERT INTO sites (name, config) VALUES ('2bess_1pv', $site${
  "schema_version": 1,
  "site": {
    "name": "Reference site: 2 x 2.5 MW / 10 MWh BESS + 5 MWac PV + 3 MW load"
  },
  "simulation": {
    "step_s": 1.0,
    "start_time": "2026-06-21T06:00:00Z",
    "autostart": true,
    "test_mode": false,
    "seed": 42,
    "history_size": 3600
  },
  "grid": {
    "vn_kv": 12.47,
    "vm_pu": 1.0,
    "va_degree": 0.0,
    "sc_mva": 100.0,
    "x_r": 5.0
  },
  "poi": {
    "line": {
      "length_km": 0.5,
      "r_ohm_per_km": 0.306,
      "x_ohm_per_km": 0.35,
      "c_nf_per_km": 0.0,
      "max_i_ka": 0.6
    }
  },
  "collectors": [
    {
      "id": "mv1",
      "feeder": null
    }
  ],
  "bess": [
    {
      "id": "bess1",
      "name": "BESS 1",
      "collector": "mv1",
      "inverter": {
        "s_rated_kva": 2750.0,
        "p_discharge_max_kw": 2500.0,
        "p_charge_max_kw": 2500.0,
        "v_lv_kv": 0.48,
        "priority": "p",
        "ramp_kw_per_s": 500.0
      },
      "battery": {
        "capacity_kwh": 10000.0,
        "soc_min_pct": 5.0,
        "soc_max_pct": 95.0,
        "soc_initial_pct": 50.0,
        "efficiency": {
          "charge": 0.95,
          "discharge": 0.95,
          "round_trip": null
        },
        "aux_load_kw": 15.0
      },
      "transformer": {
        "s_rated_kva": 2750.0,
        "vn_hv_kv": 12.47,
        "vn_lv_kv": 0.48,
        "z_pct": 5.75,
        "x_r": 7.0,
        "no_load_loss_kw": 2.5,
        "i0_pct": 0.2
      }
    },
    {
      "id": "bess2",
      "name": "BESS 2",
      "collector": "mv1",
      "inverter": {
        "s_rated_kva": 2750.0,
        "p_discharge_max_kw": 2500.0,
        "p_charge_max_kw": 2500.0,
        "v_lv_kv": 0.48,
        "priority": "p",
        "ramp_kw_per_s": 500.0
      },
      "battery": {
        "capacity_kwh": 10000.0,
        "soc_min_pct": 5.0,
        "soc_max_pct": 95.0,
        "soc_initial_pct": 50.0,
        "efficiency": {
          "charge": 0.95,
          "discharge": 0.95,
          "round_trip": null
        },
        "aux_load_kw": 15.0
      },
      "transformer": {
        "s_rated_kva": 2750.0,
        "vn_hv_kv": 12.47,
        "vn_lv_kv": 0.48,
        "z_pct": 5.75,
        "x_r": 7.0,
        "no_load_loss_kw": 2.5,
        "i0_pct": 0.2
      }
    }
  ],
  "pv": [
    {
      "id": "pv1",
      "name": "PV 1",
      "collector": "mv1",
      "dc_kwp": 6500.0,
      "loss_factor": 0.0,
      "inverter": {
        "s_rated_kva": 5500.0,
        "p_max_kw": 5000.0,
        "v_lv_kv": 0.48,
        "priority": "p"
      },
      "availability": {
        "scenario": "clear_sky_high",
        "scale": 1.0,
        "loop": true,
        "source": "ac_kw"
      },
      "transformer": {
        "s_rated_kva": 5500.0,
        "vn_hv_kv": 12.47,
        "vn_lv_kv": 0.48,
        "z_pct": 6.0,
        "x_r": 8.0,
        "no_load_loss_kw": 4.5,
        "i0_pct": 0.2
      }
    }
  ],
  "loads": [
    {
      "id": "load1",
      "name": "Site load",
      "bus": "poi",
      "profile": {
        "scenario": "high_demand",
        "scale": 1.0,
        "loop": true
      },
      "noise": {
        "p_std_pct": 1.0,
        "q_std_pct": 1.0
      },
      "transformer": null
    }
  ],
  "meters": [
    {
      "id": "m_bess1",
      "name": "m:bess1",
      "transformer": "bess1"
    },
    {
      "id": "m_bess2",
      "name": "m:bess2",
      "transformer": "bess2"
    },
    {
      "id": "m_pv1",
      "name": "m:pv1",
      "transformer": "pv1"
    }
  ],
  "interfaces": {
    "http": {
      "enabled": true
    },
    "modbus": {
      "enabled": true
    },
    "dnp3": {
      "enabled": false
    }
  }
}$site$::jsonb)
ON CONFLICT (name) DO UPDATE SET config = EXCLUDED.config, updated_at = now();

INSERT INTO sites (name, config) VALUES ('1bess_1pv', $site${
  "schema_version": 1,
  "site": {
    "name": "Small site: 1 x 2.5 MW / 10 MWh BESS + 5 MWac PV (irradiance) + load"
  },
  "simulation": {
    "step_s": 1.0,
    "start_time": "2026-06-21T06:00:00Z",
    "autostart": true,
    "test_mode": false,
    "seed": 1,
    "history_size": 3600
  },
  "grid": {
    "vn_kv": 12.47,
    "vm_pu": 1.0,
    "va_degree": 0.0,
    "sc_mva": 100.0,
    "x_r": 5.0
  },
  "poi": {
    "line": null
  },
  "collectors": [
    {
      "id": "mv1",
      "feeder": null
    }
  ],
  "bess": [
    {
      "id": "bess1",
      "name": null,
      "collector": "mv1",
      "inverter": {
        "s_rated_kva": 2750.0,
        "p_discharge_max_kw": 2500.0,
        "p_charge_max_kw": 2500.0,
        "v_lv_kv": 0.69,
        "priority": "p",
        "ramp_kw_per_s": 500.0
      },
      "battery": {
        "capacity_kwh": 10000.0,
        "soc_min_pct": 5.0,
        "soc_max_pct": 95.0,
        "soc_initial_pct": 50.0,
        "efficiency": {
          "charge": null,
          "discharge": null,
          "round_trip": 0.9
        },
        "aux_load_kw": 0.0
      },
      "transformer": {
        "s_rated_kva": 2750.0,
        "vn_hv_kv": 12.47,
        "vn_lv_kv": 0.69,
        "z_pct": 5.75,
        "x_r": 7.0,
        "no_load_loss_kw": 0.0,
        "i0_pct": 0.0
      }
    }
  ],
  "pv": [
    {
      "id": "pv1",
      "name": null,
      "collector": "mv1",
      "dc_kwp": 6500.0,
      "loss_factor": 0.05,
      "inverter": {
        "s_rated_kva": 5500.0,
        "p_max_kw": 5000.0,
        "v_lv_kv": 0.69,
        "priority": "p"
      },
      "availability": {
        "scenario": "cloudy_dynamic",
        "scale": 1.0,
        "loop": true,
        "source": "irradiance"
      },
      "transformer": {
        "s_rated_kva": 5500.0,
        "vn_hv_kv": 12.47,
        "vn_lv_kv": 0.69,
        "z_pct": 6.0,
        "x_r": 8.0,
        "no_load_loss_kw": 0.0,
        "i0_pct": 0.0
      }
    }
  ],
  "loads": [
    {
      "id": "load1",
      "name": null,
      "bus": "poi",
      "profile": {
        "scenario": "low_demand",
        "scale": 1.0,
        "loop": true
      },
      "noise": null,
      "transformer": null
    }
  ],
  "meters": [],
  "interfaces": {
    "http": {
      "enabled": true
    },
    "modbus": {
      "enabled": false
    },
    "dnp3": {
      "enabled": false
    }
  }
}$site$::jsonb)
ON CONFLICT (name) DO UPDATE SET config = EXCLUDED.config, updated_at = now();

INSERT INTO sites (name, config) VALUES ('3bess_2pv', $site${
  "schema_version": 1,
  "site": {
    "name": "3 x BESS + 2 x PV on two collectors, load behind its own transformer"
  },
  "simulation": {
    "step_s": 1.0,
    "start_time": "2026-06-21T06:00:00Z",
    "autostart": true,
    "test_mode": false,
    "seed": 7,
    "history_size": 3600
  },
  "grid": {
    "vn_kv": 12.47,
    "vm_pu": 1.0,
    "va_degree": 0.0,
    "sc_mva": 100.0,
    "x_r": 5.0
  },
  "poi": {
    "line": {
      "length_km": 0.5,
      "r_ohm_per_km": 0.306,
      "x_ohm_per_km": 0.35,
      "c_nf_per_km": 0.0,
      "max_i_ka": 0.6
    }
  },
  "collectors": [
    {
      "id": "mv1",
      "feeder": {
        "length_km": 0.3,
        "r_ohm_per_km": 0.206,
        "x_ohm_per_km": 0.33,
        "c_nf_per_km": 250.0,
        "max_i_ka": 0.5
      }
    },
    {
      "id": "mv2",
      "feeder": {
        "length_km": 0.8,
        "r_ohm_per_km": 0.206,
        "x_ohm_per_km": 0.33,
        "c_nf_per_km": 250.0,
        "max_i_ka": 0.5
      }
    }
  ],
  "bess": [
    {
      "id": "bess1",
      "name": null,
      "collector": "mv1",
      "inverter": {
        "s_rated_kva": 2750.0,
        "p_discharge_max_kw": 2500.0,
        "p_charge_max_kw": 2500.0,
        "v_lv_kv": 0.69,
        "priority": "p",
        "ramp_kw_per_s": 500.0
      },
      "battery": {
        "capacity_kwh": 10000.0,
        "soc_min_pct": 5.0,
        "soc_max_pct": 95.0,
        "soc_initial_pct": 50.0,
        "efficiency": {
          "charge": 0.95,
          "discharge": 0.95,
          "round_trip": null
        },
        "aux_load_kw": 15.0
      },
      "transformer": {
        "s_rated_kva": 2750.0,
        "vn_hv_kv": 12.47,
        "vn_lv_kv": 0.69,
        "z_pct": 5.75,
        "x_r": 7.0,
        "no_load_loss_kw": 2.5,
        "i0_pct": 0.2
      }
    },
    {
      "id": "bess2",
      "name": null,
      "collector": "mv1",
      "inverter": {
        "s_rated_kva": 2750.0,
        "p_discharge_max_kw": 2500.0,
        "p_charge_max_kw": 2500.0,
        "v_lv_kv": 0.69,
        "priority": "p",
        "ramp_kw_per_s": 500.0
      },
      "battery": {
        "capacity_kwh": 10000.0,
        "soc_min_pct": 5.0,
        "soc_max_pct": 95.0,
        "soc_initial_pct": 70.0,
        "efficiency": {
          "charge": 0.95,
          "discharge": 0.95,
          "round_trip": null
        },
        "aux_load_kw": 15.0
      },
      "transformer": {
        "s_rated_kva": 2750.0,
        "vn_hv_kv": 12.47,
        "vn_lv_kv": 0.69,
        "z_pct": 5.75,
        "x_r": 7.0,
        "no_load_loss_kw": 2.5,
        "i0_pct": 0.2
      }
    },
    {
      "id": "bess3",
      "name": null,
      "collector": "mv2",
      "inverter": {
        "s_rated_kva": 2750.0,
        "p_discharge_max_kw": 2500.0,
        "p_charge_max_kw": 2500.0,
        "v_lv_kv": 0.69,
        "priority": "p",
        "ramp_kw_per_s": 500.0
      },
      "battery": {
        "capacity_kwh": 10000.0,
        "soc_min_pct": 5.0,
        "soc_max_pct": 95.0,
        "soc_initial_pct": 90.0,
        "efficiency": {
          "charge": 0.95,
          "discharge": 0.95,
          "round_trip": null
        },
        "aux_load_kw": 15.0
      },
      "transformer": {
        "s_rated_kva": 2750.0,
        "vn_hv_kv": 12.47,
        "vn_lv_kv": 0.69,
        "z_pct": 5.75,
        "x_r": 7.0,
        "no_load_loss_kw": 2.5,
        "i0_pct": 0.2
      }
    }
  ],
  "pv": [
    {
      "id": "pv1",
      "name": null,
      "collector": "mv1",
      "dc_kwp": 3250.0,
      "loss_factor": 0.0,
      "inverter": {
        "s_rated_kva": 2750.0,
        "p_max_kw": 2500.0,
        "v_lv_kv": 0.69,
        "priority": "p"
      },
      "availability": {
        "scenario": "clear_sky_high",
        "scale": 0.5,
        "loop": true,
        "source": "ac_kw"
      },
      "transformer": {
        "s_rated_kva": 2750.0,
        "vn_hv_kv": 12.47,
        "vn_lv_kv": 0.69,
        "z_pct": 6.0,
        "x_r": 8.0,
        "no_load_loss_kw": 2.5,
        "i0_pct": 0.2
      }
    },
    {
      "id": "pv2",
      "name": null,
      "collector": "mv2",
      "dc_kwp": 3250.0,
      "loss_factor": 0.0,
      "inverter": {
        "s_rated_kva": 2750.0,
        "p_max_kw": 2500.0,
        "v_lv_kv": 0.69,
        "priority": "p"
      },
      "availability": {
        "scenario": "clear_sky_high",
        "scale": 0.5,
        "loop": true,
        "source": "ac_kw"
      },
      "transformer": {
        "s_rated_kva": 2750.0,
        "vn_hv_kv": 12.47,
        "vn_lv_kv": 0.69,
        "z_pct": 6.0,
        "x_r": 8.0,
        "no_load_loss_kw": 2.5,
        "i0_pct": 0.2
      }
    }
  ],
  "loads": [
    {
      "id": "load1",
      "name": null,
      "bus": "poi",
      "profile": {
        "scenario": "evening_peak",
        "scale": 1.0,
        "loop": true
      },
      "noise": {
        "p_std_pct": 1.0,
        "q_std_pct": 1.0
      },
      "transformer": {
        "s_rated_kva": 4000.0,
        "vn_hv_kv": 12.47,
        "vn_lv_kv": 0.48,
        "z_pct": 5.75,
        "x_r": 6.0,
        "no_load_loss_kw": 3.5,
        "i0_pct": 0.3
      }
    }
  ],
  "meters": [],
  "interfaces": {
    "http": {
      "enabled": true
    },
    "modbus": {
      "enabled": false
    },
    "dnp3": {
      "enabled": false
    }
  }
}$site$::jsonb)
ON CONFLICT (name) DO UPDATE SET config = EXCLUDED.config, updated_at = now();

-- The site loaded at startup (kept if one is already chosen).
INSERT INTO app_state (key, value) VALUES ('active_site', '{"site": "2bess_1pv"}'::jsonb)
ON CONFLICT (key) DO NOTHING;
