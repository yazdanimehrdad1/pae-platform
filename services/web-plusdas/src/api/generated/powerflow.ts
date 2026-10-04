// GENERATED from contracts/openapi/powerflow.openapi.json by scripts/api-types.mjs.
// Do not edit: run `make api-types`. Import it as `@contracts/powerflow`.

export interface paths {
    "/api/assets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** All assets, static parameters */
        get: operations["list_assets_api_assets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/bess/{asset_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Bess */
        get: operations["get_bess_api_assets_bess__asset_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/bess/{asset_id}/setpoint": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set a BESS's P/Q/mode (+P discharge, −P charge)
         * @description Partial update: omitted fields keep their value. Invalid values → 422; out-of-range values are clamped to the static limits (P ratings, S circle) and reported in `flags`. SOC and ramp limits apply every step and show up in the measurements' `limit_flags`.
         */
        put: operations["put_bess_setpoint_api_assets_bess__asset_id__setpoint_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/load/{asset_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Load */
        get: operations["get_load_api_assets_load__asset_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/pv/{asset_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Pv */
        get: operations["get_pv_api_assets_pv__asset_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/assets/pv/{asset_id}/setpoint": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set a PV's curtailment (kW or %) and Q or power factor
         * @description Partial update: omitted fields keep their value. Invalid values → 422; out-of-range values are clamped to the static limits (P ratings, S circle) and reported in `flags`. SOC and ramp limits apply every step and show up in the measurements' `limit_flags`.
         */
        put: operations["put_pv_setpoint_api_assets_pv__asset_id__setpoint_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/config": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * The active site config
         * @description To change it: PUT /api/sites/{name}, then POST /api/sites/{name}/activate.
         */
        get: operations["get_config_api_config_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/config/schema": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** JSON Schema of a site config */
        get: operations["config_schema_api_config_schema_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/defaults": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * The shipped default sites and Modbus maps
         * @description Seeded into an empty database at startup. Restore them with POST /api/defaults/restore.
         */
        get: operations["get_defaults_api_defaults_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/defaults/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Import the default sites and maps into the database
         * @description Without overwrite, sites and maps already stored are kept (reported as skipped). With overwrite=true they're replaced; the simulation must be stopped (409), and the active site is reloaded if it was replaced. The active-site choice is unchanged.
         */
        post: operations["restore_defaults_api_defaults_restore_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Liveness */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/measurements/history": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Snapshots from the in-memory ring buffer, as rows of point values */
        get: operations["history_api_measurements_history_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/measurements/latest": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * The full latest snapshot
         * @description POI, every bus, every transformer, every asset (commanded vs actual), losses and the convergence flag. `step_id` increases by one per sim tick, so a poller can spot missed steps and backfill from /measurements/history.
         */
        get: operations["latest_api_measurements_latest_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/measurements/poi": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The POI meter */
        get: operations["poi_api_measurements_poi_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/modbus/registers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Register layout of the Modbus server for the active site
         * @description One aggregator device (one port, one unit id); each device owns a 100-register chunk. `powerflow_server` says whether a point is served (yes / calc) or always reads 0 (no).
         */
        get: operations["modbus_registers_api_modbus_registers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/points": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Protocol-neutral point lists */
        get: operations["list_points_api_points_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/points/{name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read one point by name, e.g. bess.bess1.soc_pct */
        get: operations["read_point_api_points__name__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/profiles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Profile scenarios */
        get: operations["list_profiles_api_profiles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/profiles/{folder}/{scenario}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** A profile scenario's CSV */
        get: operations["get_profile_api_profiles__folder___scenario__get"];
        /**
         * Create or replace a profile scenario (CSV body)
         * @description Validated before it's written. Active-site assets using the scenario pick it up on the next step, even while running (their configured scale/loop still apply).
         */
        put: operations["put_profile_api_profiles__folder___scenario__put"];
        post?: never;
        /** Delete a profile scenario (409 while any stored site uses it) */
        delete: operations["delete_profile_api_profiles__folder___scenario__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/schemas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Stored JSON Schemas */
        get: operations["list_schemas_api_schemas_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/schemas/{name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** One JSON Schema, e.g. site-config or modbus-map */
        get: operations["get_schema_api_schemas__name__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sim/pause": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Pause */
        post: operations["pause_api_sim_pause_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sim/reset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Stop and return to the initial state */
        post: operations["reset_api_sim_reset_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sim/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start or resume real-time */
        post: operations["start_api_sim_start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sim/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Engine state and counters */
        get: operations["status_api_sim_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sim/step": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Advance N steps at once (test mode only)
         * @description Only with `simulation.test_mode: true` and while not running; otherwise 409. Returns the last step's snapshot.
         */
        post: operations["step_api_sim_step_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sim/stop": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Stop (state kept) */
        post: operations["stop_api_sim_stop_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sites": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Stored sites */
        get: operations["list_sites_api_sites_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sites/{name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Site */
        get: operations["get_site_api_sites__name__get"];
        /**
         * Create or replace a stored site
         * @description Validated (schema, references, profile scenarios exist) before it's written. Saving the active site reloads it, so the simulation must be stopped (409 otherwise).
         */
        put: operations["put_site_api_sites__name__put"];
        post?: never;
        /** Delete a site */
        delete: operations["delete_site_api_sites__name__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sites/{name}/activate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Load a stored site (only while stopped)
         * @description Rebuilds the network, resets the simulation and records the site as the one to load at startup. The engine stays stopped: POST /api/sim/start.
         */
        post: operations["activate_site_api_sites__name__activate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sites/{site}/modbus-maps": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** A site's per-asset Modbus maps */
        get: operations["list_maps_api_sites__site__modbus_maps_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sites/{site}/modbus-maps/{asset}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** One asset's map (asset = <asset_type>.<asset_id>, e.g. pv.pv1, poi.meter) */
        get: operations["get_map_api_sites__site__modbus_maps__asset__get"];
        /**
         * Create or replace an asset's map
         * @description Rejected (422) if the site has no such asset, the body's `asset` differs from the path, registers overlap, a point isn't in the asset type's point list, a writable point isn't on a holding register/coil (or vice versa), or the unit_id+port is already used by another map of the site.
         */
        put: operations["put_map_api_sites__site__modbus_maps__asset__put"];
        post?: never;
        /** Delete an asset's map */
        delete: operations["delete_map_api_sites__site__modbus_maps__asset__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/version": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Versions */
        get: operations["get_version_api_version_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * Access
         * @enum {string}
         */
        Access: "R" | "RW";
        /**
         * AssetsResponse
         * @description Every asset with its static parameters (as configured).
         */
        AssetsResponse: {
            /** Bess */
            bess: components["schemas"]["BessConfig"][];
            /** Loads */
            loads: components["schemas"]["LoadConfig"][];
            /** Meters */
            meters: components["schemas"]["MeterConfig"][];
            /** Pv */
            pv: components["schemas"]["PvConfig"][];
        };
        /** BatteryConfig */
        BatteryConfig: {
            /**
             * Aux Load Kw
             * @description Auxiliary load, drawn from the LV bus (not the cells).
             * @default 0
             */
            aux_load_kw: number;
            /** Capacity Kwh */
            capacity_kwh: number;
            efficiency?: components["schemas"]["EfficiencyConfig"];
            /**
             * Soc Initial Pct
             * @default 50
             */
            soc_initial_pct: number;
            /**
             * Soc Max Pct
             * @default 95
             */
            soc_max_pct: number;
            /**
             * Soc Min Pct
             * @default 5
             */
            soc_min_pct: number;
        };
        /** BessAssetResponse */
        BessAssetResponse: {
            config: components["schemas"]["BessConfig"];
            /** @description null before the first step. */
            measurement: components["schemas"]["BessMeasurement"] | null;
            setpoint: components["schemas"]["BessSetpointState"];
        };
        /** BessConfig */
        BessConfig: {
            battery: components["schemas"]["BatteryConfig"];
            /**
             * Collector
             * @default mv1
             */
            collector: string;
            /** Id */
            id: string;
            inverter: components["schemas"]["BessInverterConfig"];
            /** Name */
            name?: string | null;
            transformer: components["schemas"]["TransformerConfig"];
        };
        /** BessInverterConfig */
        BessInverterConfig: {
            /** P Charge Max Kw */
            p_charge_max_kw: number;
            /** P Discharge Max Kw */
            p_discharge_max_kw: number;
            /** @default p */
            priority: components["schemas"]["Priority"];
            /**
             * Ramp Kw Per S
             * @description null = unlimited.
             */
            ramp_kw_per_s?: number | null;
            /** S Rated Kva */
            s_rated_kva: number;
            /**
             * V Lv Kv
             * @default 0.69
             */
            v_lv_kv: number;
        };
        /**
         * BessMeasurement
         * @description Generator convention: P > 0 discharging.
         */
        BessMeasurement: {
            /** Alarm Flag Names */
            alarm_flag_names: string[];
            /** Alarm Flags */
            alarm_flags: number;
            /** Aux P Kw */
            aux_p_kw: number;
            /** Energy Available Charge Kwh */
            energy_available_charge_kwh: number;
            /** Energy Available Discharge Kwh */
            energy_available_discharge_kwh: number;
            /** Id */
            id: string;
            /** Limit Flag Names */
            limit_flag_names: string[];
            /** Limit Flags */
            limit_flags: number;
            /** Operating State */
            operating_state: number;
            /** Operating State Name */
            operating_state_name: string;
            /** P Available Charge Kw */
            p_available_charge_kw: number;
            /** P Available Discharge Kw */
            p_available_discharge_kw: number;
            /** P Cmd Kw */
            p_cmd_kw: number;
            /** P Kw */
            p_kw: number;
            /** Q Cmd Kvar */
            q_cmd_kvar: number;
            /** Q Kvar */
            q_kvar: number;
            /** S Kva */
            s_kva: number;
            /** Soc Pct */
            soc_pct: number;
            /** Status */
            status: number;
            /** Status Name */
            status_name: string;
            /** V Lv Kv */
            v_lv_kv: number;
            /** V Lv Pu */
            v_lv_pu: number;
        };
        /**
         * BessMode
         * @enum {string}
         */
        BessMode: "idle" | "pq" | "offline";
        /**
         * BessSetpointRequest
         * @description A partial BESS setpoint: omitted fields keep their current value.
         */
        BessSetpointRequest: {
            mode?: components["schemas"]["BessMode"] | null;
            /**
             * P Kw
             * @description + discharge, − charge (kW).
             */
            p_kw?: number | null;
            /**
             * Q Kvar
             * @description + injecting vars (kvar).
             */
            q_kvar?: number | null;
        };
        /** BessSetpointState */
        BessSetpointState: {
            mode: components["schemas"]["BessMode"];
            /** P Kw */
            p_kw: number;
            /** Q Kvar */
            q_kvar: number;
        };
        /** BusMeasurement */
        BusMeasurement: {
            /** Angle Deg */
            angle_deg: number;
            /** Name */
            name: string;
            /**
             * V Kv
             * @description Line-to-line voltage (kV).
             */
            v_kv: number;
            /** V Pu */
            v_pu: number;
            /** Vn Kv */
            vn_kv: number;
        };
        /**
         * CollectorConfig
         * @description An MV collector bus. Without a feeder it is tied to the POI bus by a closed switch.
         */
        CollectorConfig: {
            feeder?: components["schemas"]["LineConfig"] | null;
            /** Id */
            id: string;
        };
        /**
         * DataType
         * @enum {string}
         */
        DataType: "float32" | "uint16" | "uint32" | "uint64" | "enum16" | "bitfield16";
        /** DefaultsInfo */
        DefaultsInfo: {
            /**
             * Active Site
             * @description The site made active on a fresh database.
             */
            active_site: string;
            /**
             * Sites
             * @description Default sites and their Modbus map assets.
             */
            sites: {
                [key: string]: string[];
            };
        };
        /** DefaultsRestoreResult */
        DefaultsRestoreResult: {
            /** Active Site Reloaded */
            active_site_reloaded: boolean;
            /** Maps Skipped */
            maps_skipped: string[];
            /** Maps Written */
            maps_written: string[];
            /** Overwrite */
            overwrite: boolean;
            /**
             * Sites Skipped
             * @description Already stored; pass overwrite=true.
             */
            sites_skipped: string[];
            /** Sites Written */
            sites_written: string[];
        };
        /**
         * DeviceKind
         * @enum {string}
         */
        DeviceKind: "site" | "met_station" | "bess" | "pv" | "load" | "poi_meter" | "feeder_meter";
        /**
         * EfficiencyConfig
         * @description Either charge + discharge efficiencies, or a round-trip efficiency split evenly.
         */
        EfficiencyConfig: {
            /** Charge */
            charge?: number | null;
            /** Discharge */
            discharge?: number | null;
            /** Round Trip */
            round_trip?: number | null;
        };
        /** EngineStatus */
        EngineStatus: {
            /** History Count */
            history_count: number;
            /** History Size */
            history_size: number;
            /** Last Converged */
            last_converged: boolean | null;
            /** Last Step Duration Ms */
            last_step_duration_ms: number | null;
            /** Nonconverged Count */
            nonconverged_count: number;
            /** Overrun Count */
            overrun_count: number;
            /**
             * Sim Time
             * Format: date-time
             */
            sim_time: string;
            state: components["schemas"]["RunState"];
            /** Step Id */
            step_id: number;
            /** Step S */
            step_s: number;
            /** Test Mode */
            test_mode: boolean;
        };
        /** ErrorResponse */
        ErrorResponse: {
            /** Detail */
            detail: string;
        };
        /**
         * GridConfig
         * @description The utility feeder: an ideal source behind its short-circuit impedance.
         */
        GridConfig: {
            /**
             * Sc Mva
             * @description Short-circuit power at the POI.
             * @default 100
             */
            sc_mva: number;
            /**
             * Va Degree
             * @description Source voltage angle (deg).
             * @default 0
             */
            va_degree: number;
            /**
             * Vm Pu
             * @description Source voltage (pu).
             * @default 1
             */
            vm_pu: number;
            /**
             * Vn Kv
             * @description Nominal voltage, line-to-line (kV).
             * @default 12.47
             */
            vn_kv: number;
            /**
             * X R
             * @description Source impedance X/R ratio.
             * @default 5
             */
            x_r: number;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HealthResponse */
        HealthResponse: {
            /** Ok */
            ok: boolean;
            state: components["schemas"]["RunState"];
        };
        /**
         * HistoryFormat
         * @enum {string}
         */
        HistoryFormat: "json" | "csv";
        /** HistoryResponse */
        HistoryResponse: {
            /** Count */
            count: number;
            /** Fields */
            fields: string[];
            /**
             * Rows
             * @description One row per snapshot: sim_time, step_id and the requested fields.
             */
            rows: {
                [key: string]: number | string;
            }[];
        };
        /** HttpInterfaceConfig */
        HttpInterfaceConfig: {
            /**
             * Enabled
             * @default true
             * @constant
             */
            enabled: true;
        };
        /** InterfaceToggle */
        InterfaceToggle: {
            /**
             * Enabled
             * @default false
             */
            enabled: boolean;
        };
        /** InterfacesConfig */
        InterfacesConfig: {
            dnp3?: components["schemas"]["InterfaceToggle"];
            http?: components["schemas"]["HttpInterfaceConfig"];
            modbus?: components["schemas"]["ModbusInterfaceConfig"];
        };
        JsonValue: unknown;
        /** LineConfig */
        LineConfig: {
            /**
             * C Nf Per Km
             * @default 0
             */
            c_nf_per_km: number;
            /** Length Km */
            length_km: number;
            /**
             * Max I Ka
             * @default 1
             */
            max_i_ka: number;
            /** R Ohm Per Km */
            r_ohm_per_km: number;
            /** X Ohm Per Km */
            x_ohm_per_km: number;
        };
        /** LoadAssetResponse */
        LoadAssetResponse: {
            config: components["schemas"]["LoadConfig"];
            measurement: components["schemas"]["LoadMeasurement"] | null;
        };
        /** LoadConfig */
        LoadConfig: {
            /**
             * Bus
             * @description "poi" or a collector id.
             * @default poi
             */
            bus: string;
            /** Id */
            id: string;
            /** Name */
            name?: string | null;
            noise?: components["schemas"]["NoiseConfig"] | null;
            profile: components["schemas"]["ProfileRef"];
            /** @description Optional transformer; its LV side feeds the load. */
            transformer?: components["schemas"]["TransformerConfig"] | null;
        };
        /**
         * LoadMeasurement
         * @description Load convention: P > 0 consuming.
         */
        LoadMeasurement: {
            /** Alarm Flag Names */
            alarm_flag_names: string[];
            /** Alarm Flags */
            alarm_flags: number;
            /** Id */
            id: string;
            /** P Kw */
            p_kw: number;
            /** Pf */
            pf: number;
            /** Q Kvar */
            q_kvar: number;
            /** S Kva */
            s_kva: number;
            /** Supply State */
            supply_state: number;
            /** Supply State Name */
            supply_state_name: string;
            /** V Pu */
            v_pu: number;
        };
        /**
         * MeterConfig
         * @description A feeder meter on the HV side of an asset's transformer (between the MV bus and the
         *     transformer), so it reads P/Q after the transformer losses. Positive = toward the MV bus.
         */
        MeterConfig: {
            /** Id */
            id: string;
            /** Name */
            name?: string | null;
            /**
             * Transformer
             * @description The BESS, PV or load (with a transformer) whose transformer is metered.
             */
            transformer: string;
        };
        /**
         * MeterMeasurement
         * @description A feeder meter on the HV side of an asset's transformer. Positive P/Q = toward the MV
         *     bus (after the transformer losses).
         */
        MeterMeasurement: {
            /**
             * I A
             * @description Current on the transformer's HV side.
             */
            i_a: number;
            /** Id */
            id: string;
            /** Meter State */
            meter_state: number;
            /** Meter State Name */
            meter_state_name: string;
            /** P Kw */
            p_kw: number;
            /**
             * Pf
             * @description |P|/S signed with Q (positive = vars toward the MV bus).
             */
            pf: number;
            /** Q Kvar */
            q_kvar: number;
            /** S Kva */
            s_kva: number;
            /**
             * Transformer
             * @description The asset whose transformer is metered.
             */
            transformer: string;
            /**
             * V Kv
             * @description MV bus voltage, line-to-line.
             */
            v_kv: number;
            /** V Pu */
            v_pu: number;
        };
        /**
         * ModbusDataType
         * @enum {string}
         */
        ModbusDataType: "bool" | "int16" | "uint16" | "int32" | "uint32" | "float32" | "uint64";
        /** ModbusDevice */
        ModbusDevice: {
            /** Asset Id */
            asset_id: string;
            /** Base */
            base: number;
            kind: components["schemas"]["DeviceKind"];
            /** Registers */
            registers: components["schemas"]["ModbusRegister"][];
        };
        /**
         * ModbusInterfaceConfig
         * @description The maps are the files in site_config/modbus_maps/<site>/ (one per asset).
         */
        ModbusInterfaceConfig: {
            /**
             * Enabled
             * @default false
             */
            enabled: boolean;
        };
        /**
         * ModbusMap
         * @description One asset's map. `asset` is `<asset_type>.<asset_id>`, e.g. `bess.bess1`.
         */
        ModbusMap: {
            /** Asset */
            asset: string;
            /**
             * Map Version
             * @default 1
             * @constant
             */
            map_version: 1;
            /** Points */
            points: components["schemas"]["ModbusPointMap"][];
            /**
             * Port
             * @default 502
             */
            port: number;
            /**
             * Register Numbering
             * @default zero_based
             * @enum {string}
             */
            register_numbering: "zero_based" | "one_based";
            /** Unit Id */
            unit_id: number;
        };
        /** ModbusMapSummary */
        ModbusMapSummary: {
            /** Asset */
            asset: string;
            /**
             * Orphaned
             * @description True if the site no longer has this asset.
             */
            orphaned: boolean;
            /** Points */
            points: number;
            /** Port */
            port: number;
            /** Unit Id */
            unit_id: number;
        };
        /** ModbusPointMap */
        ModbusPointMap: {
            /** Address */
            address: number;
            /**
             * Bit Flags
             * @description For an alarm/flag word: bit number (0 = LSB) → flag name.
             */
            bit_flags?: {
                [key: string]: string;
            } | null;
            data_type: components["schemas"]["ModbusDataType"];
            /**
             * Enum Values
             * @description For a status enum: register value → state name.
             */
            enum_values?: {
                [key: string]: string;
            } | null;
            /**
             * Point
             * @description Point name from the asset type's point list.
             */
            point: string;
            register_type: components["schemas"]["RegisterType"];
            /**
             * Scale
             * @description Engineering value = raw × scale.
             * @default 1
             */
            scale: number;
            /** @default big */
            word_order: components["schemas"]["WordOrder"];
        };
        /** ModbusRegister */
        ModbusRegister: {
            /**
             * Address
             * @description Zero-based register address (holding and input alike).
             */
            address: number;
            /** Data Type */
            data_type: string;
            /**
             * Point
             * @description Point name from the PAE point standard.
             */
            point: string;
            powerflow_server: components["schemas"]["ServerSupport"];
            /**
             * Scale
             * @description Engineering value = raw × scale.
             */
            scale: number;
            /** Unit */
            unit: string;
        };
        /**
         * ModbusRegistersResponse
         * @description The Modbus server's register layout for the active site.
         */
        ModbusRegistersResponse: {
            /** Devices */
            devices: components["schemas"]["ModbusDevice"][];
            /**
             * Enabled
             * @description Whether the active site enables interfaces.modbus.
             */
            enabled: boolean;
            /**
             * Port
             * @description The port the server listens on (inside the container).
             */
            port: number;
            /** Unit Id */
            unit_id: number;
        };
        /** NoiseConfig */
        NoiseConfig: {
            /**
             * P Std Pct
             * @default 0
             */
            p_std_pct: number;
            /**
             * Q Std Pct
             * @default 0
             */
            q_std_pct: number;
        };
        /** PoiConfig */
        PoiConfig: {
            /** @description Optional POI line/cable between the POI and the grid. */
            line?: components["schemas"]["LineConfig"] | null;
        };
        /**
         * PoiMeasurement
         * @description The POI meter. Positive P/Q = export to the utility.
         */
        PoiMeasurement: {
            /** Alarm Flag Names */
            alarm_flag_names: string[];
            /** Alarm Flags */
            alarm_flags: number;
            /** Angle Deg */
            angle_deg: number;
            /** I A */
            i_a: number;
            /** Meter State */
            meter_state: number;
            /** Meter State Name */
            meter_state_name: string;
            /** P Kw */
            p_kw: number;
            /**
             * P Loss Total Kw
             * @description Site losses: transformers + collector feeders.
             */
            p_loss_total_kw: number;
            /**
             * Pf
             * @description |P|/S signed with Q (positive = exporting vars).
             */
            pf: number;
            /** Q Kvar */
            q_kvar: number;
            /** Q Loss Total Kvar */
            q_loss_total_kvar: number;
            /** S Kva */
            s_kva: number;
            /** V Kv */
            v_kv: number;
            /** V Pu */
            v_pu: number;
        };
        /** PoiResponse */
        PoiResponse: {
            /** Converged */
            converged: boolean;
            poi: components["schemas"]["PoiMeasurement"];
            /**
             * Sim Time
             * Format: date-time
             */
            sim_time: string;
            /** Step Id */
            step_id: number;
        };
        /** PointDef */
        PointDef: {
            access: components["schemas"]["Access"];
            /** Bit Flags */
            bit_flags?: {
                [key: string]: string;
            } | null;
            data_type: components["schemas"]["DataType"];
            /** Description */
            description: string;
            /** Enum Values */
            enum_values?: {
                [key: string]: string;
            } | null;
            /** Name */
            name: string;
            /** Scale Hint */
            scale_hint?: number | null;
            source: components["schemas"]["PointSource"];
            /** Unit */
            unit: string;
        };
        /**
         * PointSource
         * @description Where a point's value comes from.
         * @enum {string}
         */
        PointSource: "measurement" | "setpoint" | "nameplate" | "simulation";
        /** PointValueResponse */
        PointValueResponse: {
            /** Name */
            name: string;
            /** Unit */
            unit: string;
            /** Value */
            value: number;
        };
        /** PointsResponse */
        PointsResponse: {
            /**
             * Names
             * @description Every point name for the current site config.
             */
            names: string[];
            /**
             * Naming
             * @default <asset_type>.<asset_id>.<point>
             */
            naming: string;
            /** Point Lists */
            point_lists: {
                [key: string]: components["schemas"]["PointDef"][];
            };
        };
        /**
         * Priority
         * @description Which of P and Q is kept when a setpoint exceeds the apparent power rating.
         * @enum {string}
         */
        Priority: "p" | "q";
        /**
         * ProfileFolder
         * @enum {string}
         */
        ProfileFolder: "load" | "pv";
        /** ProfileRef */
        ProfileRef: {
            /**
             * Loop
             * @description Repeat the profile; else hold the ends.
             * @default true
             */
            loop: boolean;
            /**
             * Scale
             * @description Multiplies every profile value.
             * @default 1
             */
            scale: number;
            /**
             * Scenario
             * @description Profile scenario: a CSV in site_config/profiles/<load|pv>/<scenario>.csv.
             */
            scenario: string;
        };
        /** ProfileSaveResult */
        ProfileSaveResult: {
            /** Columns */
            columns: string[];
            /**
             * End
             * Format: date-time
             */
            end: string;
            folder: components["schemas"]["ProfileFolder"];
            /**
             * Reloaded Assets
             * @description Active-site assets now using the new data.
             */
            reloaded_assets: string[];
            /** Rows */
            rows: number;
            /** Scenario */
            scenario: string;
            /**
             * Start
             * Format: date-time
             */
            start: string;
        };
        /** ProfileScenarios */
        ProfileScenarios: {
            /** Load */
            load: string[];
            /** Pv */
            pv: string[];
        };
        /** PvAssetResponse */
        PvAssetResponse: {
            config: components["schemas"]["PvConfig"];
            measurement: components["schemas"]["PvMeasurement"] | null;
            setpoint: components["schemas"]["PvSetpointState"];
        };
        /** PvAvailabilityConfig */
        PvAvailabilityConfig: {
            /**
             * Loop
             * @description Repeat the profile; else hold the ends.
             * @default true
             */
            loop: boolean;
            /**
             * Scale
             * @description Multiplies every profile value.
             * @default 1
             */
            scale: number;
            /**
             * Scenario
             * @description Profile scenario: a CSV in site_config/profiles/<load|pv>/<scenario>.csv.
             */
            scenario: string;
            /** @default ac_kw */
            source: components["schemas"]["PvAvailabilitySource"];
        };
        /**
         * PvAvailabilitySource
         * @enum {string}
         */
        PvAvailabilitySource: "ac_kw" | "irradiance";
        /** PvConfig */
        PvConfig: {
            availability: components["schemas"]["PvAvailabilityConfig"];
            /**
             * Collector
             * @default mv1
             */
            collector: string;
            /** Dc Kwp */
            dc_kwp: number;
            /** Id */
            id: string;
            inverter: components["schemas"]["PvInverterConfig"];
            /**
             * Loss Factor
             * @description Fraction lost before AC.
             * @default 0
             */
            loss_factor: number;
            /** Name */
            name?: string | null;
            transformer: components["schemas"]["TransformerConfig"];
        };
        /** PvInverterConfig */
        PvInverterConfig: {
            /** P Max Kw */
            p_max_kw: number;
            /** @default p */
            priority: components["schemas"]["Priority"];
            /** S Rated Kva */
            s_rated_kva: number;
            /**
             * V Lv Kv
             * @default 0.69
             */
            v_lv_kv: number;
        };
        /** PvMeasurement */
        PvMeasurement: {
            /** Alarm Flag Names */
            alarm_flag_names: string[];
            /** Alarm Flags */
            alarm_flags: number;
            /** Curtailment Kw */
            curtailment_kw: number;
            /** Id */
            id: string;
            /** Inverter State */
            inverter_state: number;
            /** Inverter State Name */
            inverter_state_name: string;
            /** Irradiance Wm2 */
            irradiance_wm2: number;
            /** Limit Flag Names */
            limit_flag_names: string[];
            /** Limit Flags */
            limit_flags: number;
            /** P Available Kw */
            p_available_kw: number;
            /** P Kw */
            p_kw: number;
            /** P Limit Active Kw */
            p_limit_active_kw: number;
            /** Pf */
            pf: number;
            /** Q Kvar */
            q_kvar: number;
            /** S Kva */
            s_kva: number;
            /** Status */
            status: number;
            /** Status Name */
            status_name: string;
            /** V Lv Kv */
            v_lv_kv: number;
            /** V Lv Pu */
            v_lv_pu: number;
        };
        /**
         * PvSetpointRequest
         * @description A partial PV setpoint: at most one of p_limit_kw / p_limit_pct and one of q_kvar / pf.
         *     Omitted fields keep their current value.
         */
        PvSetpointRequest: {
            /**
             * P Limit Kw
             * @description Curtailment limit (kW).
             */
            p_limit_kw?: number | null;
            /**
             * P Limit Pct
             * @description Curtailment limit (% of p_max_kw).
             */
            p_limit_pct?: number | null;
            /**
             * Pf
             * @description Power factor; + injecting vars, − absorbing; |pf| ≥ 0.8. Selects PF mode.
             */
            pf?: number | null;
            /**
             * Q Kvar
             * @description Q setpoint; selects Q mode.
             */
            q_kvar?: number | null;
        };
        /** PvSetpointState */
        PvSetpointState: {
            /** P Limit Kw */
            p_limit_kw: number;
            /** P Limit Pct */
            p_limit_pct: number;
            /** Pf */
            pf: number;
            /** Q Kvar */
            q_kvar: number;
            /**
             * Q Mode
             * @description "q" or "pf".
             */
            q_mode: string;
        };
        /**
         * RegisterType
         * @enum {string}
         */
        RegisterType: "holding" | "input" | "coil" | "discrete_input";
        /**
         * RunState
         * @enum {string}
         */
        RunState: "stopped" | "running" | "paused";
        /**
         * ServerSupport
         * @description The `powerflow_server` column: can the powerflow Modbus server fill this point?
         * @enum {string}
         */
        ServerSupport: "yes" | "calc" | "no";
        /** SetpointResult */
        SetpointResult: {
            /** Accepted */
            accepted: components["schemas"]["BessSetpointState"] | components["schemas"]["PvSetpointState"];
            /** Asset Id */
            asset_id: string;
            /** Asset Type */
            asset_type: string;
            /** Clamped */
            clamped: boolean;
            /**
             * Flags
             * @description Static limits that clamped the request.
             */
            flags: string[];
            /** Requested */
            requested: {
                [key: string]: number | string | null;
            };
        };
        /** SimulationConfig */
        SimulationConfig: {
            /**
             * Autostart
             * @description Start the real-time loop at startup.
             * @default true
             */
            autostart: boolean;
            /**
             * History Size
             * @description Snapshots kept in the history buffer.
             * @default 3600
             */
            history_size: number;
            /**
             * Seed
             * @description Seed for the load noise.
             * @default 0
             */
            seed: number;
            /**
             * Start Time
             * Format: date-time
             * @description Sim clock origin (timezone-aware ISO 8601). Sim time then advances 1:1 with wall-clock.
             * @default 2026-01-01T00:00:00Z
             */
            start_time: string;
            /**
             * Step S
             * @description Simulation step (s).
             * @default 1
             */
            step_s: number;
            /**
             * Test Mode
             * @description Enables POST /sim/step (manual stepping, tests only).
             * @default false
             */
            test_mode: boolean;
        };
        /**
         * SiteConfig
         * @description A grid-connected site: the utility feeder, the POI, MV collectors and N BESS/PV/loads.
         */
        SiteConfig: {
            /** Bess */
            bess?: components["schemas"]["BessConfig"][];
            /** Collectors */
            collectors?: components["schemas"]["CollectorConfig"][];
            grid?: components["schemas"]["GridConfig"];
            interfaces?: components["schemas"]["InterfacesConfig"];
            /** Loads */
            loads?: components["schemas"]["LoadConfig"][];
            /** Meters */
            meters?: components["schemas"]["MeterConfig"][];
            poi?: components["schemas"]["PoiConfig"];
            /** Pv */
            pv?: components["schemas"]["PvConfig"][];
            /**
             * Schema Version
             * @default 1
             * @constant
             */
            schema_version: 1;
            simulation?: components["schemas"]["SimulationConfig"];
            site?: components["schemas"]["SiteInfo"];
        };
        /** SiteInfo */
        SiteInfo: {
            /**
             * Name
             * @default Site
             */
            name: string;
        };
        /** SiteList */
        SiteList: {
            /** Active */
            active: string;
            /** Sites */
            sites: string[];
        };
        /** Snapshot */
        Snapshot: {
            /** Bess */
            bess: components["schemas"]["BessMeasurement"][];
            /** Buses */
            buses: components["schemas"]["BusMeasurement"][];
            /**
             * Converged
             * @description False: the power flow failed this step and the values are the last good ones.
             */
            converged: boolean;
            /** Loads */
            loads: components["schemas"]["LoadMeasurement"][];
            /**
             * Meters
             * @description Feeder meters, in config order.
             */
            meters: components["schemas"]["MeterMeasurement"][];
            poi: components["schemas"]["PoiMeasurement"];
            /** Pv */
            pv: components["schemas"]["PvMeasurement"][];
            /**
             * Sim Time
             * Format: date-time
             */
            sim_time: string;
            /**
             * Step Id
             * @description Sim tick number; increases by 1 per step (gaps = skipped).
             */
            step_id: number;
            /** Transformers */
            transformers: components["schemas"]["TransformerMeasurement"][];
        };
        /** TransformerConfig */
        TransformerConfig: {
            /**
             * I0 Pct
             * @description No-load current (%).
             * @default 0
             */
            i0_pct: number;
            /**
             * No Load Loss Kw
             * @default 0
             */
            no_load_loss_kw: number;
            /** S Rated Kva */
            s_rated_kva: number;
            /** Vn Hv Kv */
            vn_hv_kv: number;
            /** Vn Lv Kv */
            vn_lv_kv: number;
            /**
             * X R
             * @default 7
             */
            x_r: number;
            /**
             * Z Pct
             * @description Short-circuit impedance (%Z).
             */
            z_pct: number;
        };
        /**
         * TransformerMeasurement
         * @description Positive P/Q = flowing toward the grid (LV → HV).
         */
        TransformerMeasurement: {
            /** Loading Pct */
            loading_pct: number;
            /** Name */
            name: string;
            /**
             * P Hv Kw
             * @description P leaving at the HV terminal.
             */
            p_hv_kw: number;
            /** P Loss Kw */
            p_loss_kw: number;
            /**
             * P Lv Kw
             * @description P entering at the LV terminal.
             */
            p_lv_kw: number;
            /** Q Hv Kvar */
            q_hv_kvar: number;
            /** Q Loss Kvar */
            q_loss_kvar: number;
            /** Q Lv Kvar */
            q_lv_kvar: number;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** VersionResponse */
        VersionResponse: {
            /** Api Version */
            api_version: string;
            /** Pandapower Version */
            pandapower_version: string;
            /** Python Version */
            python_version: string;
            /** Service */
            service: string;
        };
        /**
         * WordOrder
         * @enum {string}
         */
        WordOrder: "big" | "little";
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    list_assets_api_assets_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssetsResponse"];
                };
            };
        };
    };
    get_bess_api_assets_bess__asset_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                asset_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BessAssetResponse"];
                };
            };
            /** @description Unknown asset or point. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    put_bess_setpoint_api_assets_bess__asset_id__setpoint_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                asset_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BessSetpointRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SetpointResult"];
                };
            };
            /** @description Unknown asset or point. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_load_api_assets_load__asset_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                asset_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LoadAssetResponse"];
                };
            };
            /** @description Unknown asset or point. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_pv_api_assets_pv__asset_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                asset_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PvAssetResponse"];
                };
            };
            /** @description Unknown asset or point. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    put_pv_setpoint_api_assets_pv__asset_id__setpoint_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                asset_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PvSetpointRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SetpointResult"];
                };
            };
            /** @description Unknown asset or point. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_config_api_config_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SiteConfig"];
                };
            };
        };
    };
    config_schema_api_config_schema_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: components["schemas"]["JsonValue"];
                    };
                };
            };
        };
    };
    get_defaults_api_defaults_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DefaultsInfo"];
                };
            };
        };
    };
    restore_defaults_api_defaults_restore_post: {
        parameters: {
            query?: {
                overwrite?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DefaultsRestoreResult"];
                };
            };
            /** @description No such site, map or scenario. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not allowed now (running, or in use). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid name or content. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    history_api_measurements_history_get: {
        parameters: {
            query?: {
                /** @description Sim time ≥ from. */
                from?: string | null;
                /** @description Sim time ≤ to. */
                to?: string | null;
                /** @description Comma-separated measurement point names (e.g. `poi.meter.p_kw,bess.bess1.soc_pct`). Default: every measurement point. */
                fields?: string | null;
                format?: components["schemas"]["HistoryFormat"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HistoryResponse"];
                    "text/csv": string;
                };
            };
            /** @description Unknown field. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Field is not a measurement point. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    latest_api_measurements_latest_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Snapshot"];
                };
            };
            /** @description No step has run yet. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    poi_api_measurements_poi_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PoiResponse"];
                };
            };
            /** @description No step has run yet. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    modbus_registers_api_modbus_registers_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModbusRegistersResponse"];
                };
            };
        };
    };
    list_points_api_points_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PointsResponse"];
                };
            };
        };
    };
    read_point_api_points__name__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PointValueResponse"];
                };
            };
            /** @description Unknown asset or point. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_profiles_api_profiles_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileScenarios"];
                };
            };
        };
    };
    get_profile_api_profiles__folder___scenario__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                folder: components["schemas"]["ProfileFolder"];
                scenario: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/csv": string;
                };
            };
            /** @description No such site, map or scenario. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not allowed now (running, or in use). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid name or content. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    put_profile_api_profiles__folder___scenario__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                folder: components["schemas"]["ProfileFolder"];
                scenario: string;
            };
            cookie?: never;
        };
        /** @description Load: timestamp,p_kw,q_kvar (or timestamp,p_kw,pf). PV: timestamp and p_kw (ac_kw source) and/or ghi_wm2 (irradiance source). Timestamps ISO 8601. */
        requestBody: {
            content: {
                "text/csv": string;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileSaveResult"];
                };
            };
            /** @description No such site, map or scenario. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not allowed now (running, or in use). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid name or content. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    delete_profile_api_profiles__folder___scenario__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                folder: components["schemas"]["ProfileFolder"];
                scenario: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description No such site, map or scenario. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not allowed now (running, or in use). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid name or content. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_schemas_api_schemas_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": string[];
                };
            };
        };
    };
    get_schema_api_schemas__name__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: components["schemas"]["JsonValue"];
                    };
                };
            };
            /** @description No such site, map or scenario. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not allowed now (running, or in use). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid name or content. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    pause_api_sim_pause_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EngineStatus"];
                };
            };
            /** @description Not allowed in the current state. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    reset_api_sim_reset_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EngineStatus"];
                };
            };
        };
    };
    start_api_sim_start_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EngineStatus"];
                };
            };
        };
    };
    status_api_sim_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EngineStatus"];
                };
            };
        };
    };
    step_api_sim_step_post: {
        parameters: {
            query?: {
                count?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Snapshot"];
                };
            };
            /** @description Not allowed in the current state. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    stop_api_sim_stop_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EngineStatus"];
                };
            };
        };
    };
    list_sites_api_sites_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SiteList"];
                };
            };
        };
    };
    get_site_api_sites__name__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SiteConfig"];
                };
            };
            /** @description No such site, map or scenario. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not allowed now (running, or in use). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid name or content. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    put_site_api_sites__name__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SiteConfig"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SiteConfig"];
                };
            };
            /** @description No such site, map or scenario. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not allowed now (running, or in use). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid name or content. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    delete_site_api_sites__name__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description No such site, map or scenario. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not allowed now (running, or in use). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid name or content. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    activate_site_api_sites__name__activate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SiteConfig"];
                };
            };
            /** @description No such site, map or scenario. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not allowed now (running, or in use). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid name or content. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_maps_api_sites__site__modbus_maps_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModbusMapSummary"][];
                };
            };
            /** @description No such site, map or scenario. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not allowed now (running, or in use). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid name or content. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_map_api_sites__site__modbus_maps__asset__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site: string;
                asset: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModbusMap"];
                };
            };
            /** @description No such site, map or scenario. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not allowed now (running, or in use). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid name or content. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    put_map_api_sites__site__modbus_maps__asset__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site: string;
                asset: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ModbusMap"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModbusMap"];
                };
            };
            /** @description No such site, map or scenario. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not allowed now (running, or in use). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid name or content. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    delete_map_api_sites__site__modbus_maps__asset__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site: string;
                asset: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description No such site, map or scenario. */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not allowed now (running, or in use). */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid name or content. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_version_api_version_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionResponse"];
                };
            };
        };
    };
}
