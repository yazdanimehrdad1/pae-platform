// GENERATED from contracts/openapi/backend-ot.openapi.json by scripts/api-types.mjs.
// Do not edit: run `make api-types`. Import it as `@contracts/backend-ot`.

export interface paths {
    "/api/cache/clear": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Cache Clear All
         * @description Delete all cache keys and associated data.
         *
         *     WARNING: This is a destructive operation that will permanently delete
         *     all cached data. Use with caution.
         *
         *     Returns:
         *         Dictionary with number of keys deleted
         */
        delete: operations["cache_clear_all_api_cache_clear_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cache/delete/{key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Cache Delete
         * @description Delete a key from cache.
         */
        delete: operations["cache_delete_api_cache_delete__key__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cache/exists/{key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Cache Exists
         * @description Check if a key exists in cache.
         */
        get: operations["cache_exists_api_cache_exists__key__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cache/get/{key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Cache Get
         * @description Get a value from cache.
         */
        get: operations["cache_get_api_cache_get__key__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cache/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Cache Health
         * @description Check Redis cache health.
         */
        get: operations["cache_health_api_cache_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cache/keys": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Cache List Keys
         * @description List all cached keys with TTL, optionally filtered by pattern.
         *
         *     Args:
         *         pattern: Optional pattern to match (e.g., "poll:*").
         *                 If not provided, returns all keys.
         *
         *     Returns:
         *         Dictionary with list of keys (with TTL) and count
         */
        get: operations["cache_list_keys_api_cache_keys_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cache/set": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cache Set
         * @description Set a value in cache.
         */
        post: operations["cache_set_api_cache_set_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/csv-exports/raw-register-map-csv": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Export Raw Register Map Csv
         * @description Export empty CSV file with register map column headers.
         *
         *     If type is 'modbus', exports an empty CSV file with the following columns:
         *     - register_address
         *     - register_name
         *     - size
         *     - data_type
         *     - scale_factor
         *     - unit
         *
         *     Args:
         *         type: Export type (must be 'modbus' for now)
         *
         *     Returns:
         *         Empty CSV file with column headers only
         */
        get: operations["export_raw_register_map_csv_api_csv_exports_raw_register_map_csv_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/db_health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Db Health
         * @description Database health check endpoint with detailed information.
         *
         *     Returns:
         *         Dictionary containing database connection status, configuration, and server information
         */
        get: operations["db_health_api_db_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/device-point-readings/site/{site_id}/device/{device_id}/latest": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Latest Readings
         * @description Get the latest reading for each requested device point, keyed by device_point_id.
         */
        get: operations["get_latest_readings_api_device_point_readings_site__site_id__device__device_id__latest_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/device-point-readings/timeseries/site/{site_id}/device/{device_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Timeseries Readings
         * @description Get time-series readings for each requested device point, keyed by device_point_id.
         *     Each entry contains point metadata and a timeseries array sorted newest-first —
         *     the most recent reading is always the first element, for any limit or time window.
         *
         *     Time window — pick one approach:
         *     - time_range: shorthand token (e.g. '1H', '1D', '1W') resolved relative to UTC now
         *     - start_time / end_time: ISO timestamps carrying a UTC offset
         *     - Neither: returns all stored readings up to limit
         *
         *     Timezones: readings are stored in UTC and returned in UTC by default. A timestamp
         *     without an offset is rejected rather than guessed — pass tz=<IANA zone> to read
         *     naive bounds as local wall-clock time and render the response in that zone.
         */
        get: operations["get_timeseries_readings_api_device_point_readings_timeseries_site__site_id__device__device_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/device-points/site/{site_id}/device/{device_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List a device's points
         * @description Get all registered points for a specific device.
         */
        get: operations["get_points_for_device_api_device_points_site__site_id__device__device_id__get"];
        put?: never;
        post?: never;
        /**
         * Soft- or hard-delete device points
         * @description Delete one or more device points. Returns the deleted points. Soft delete preserves readings; hard delete is permanent.
         */
        delete: operations["delete_points_api_device_points_site__site_id__device__device_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/device-points/site/{site_id}/device/{device_id}/bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Bulk create/update a device's points
         * @description Upsert multiple device points in one call.
         *     Points matched by name: existing names are updated, new names are created.
         *     Scan range recompute runs once at the end.
         */
        put: operations["bulk_upsert_points_api_device_points_site__site_id__device__device_id__bulk_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/device-points/site/{site_id}/device/{device_id}/deleted": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List a device's soft-deleted points
         * @description Get all soft-deleted points for a specific device, ordered by most recently deleted.
         */
        get: operations["get_deleted_points_for_device_api_device_points_site__site_id__device__device_id__deleted_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/device-points/site/{site_id}/device/{device_id}/scan-ranges": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Override and lock a device's scan ranges
         * @description Manually set scan ranges and lock them (auto-recompute disabled until reset).
         */
        put: operations["override_scan_ranges_api_device_points_site__site_id__device__device_id__scan_ranges_put"];
        post?: never;
        /**
         * Reset a device's scan ranges to auto-computed
         * @description Clear the scan ranges lock and recompute from current NATIVE points.
         */
        delete: operations["reset_scan_ranges_api_device_points_site__site_id__device__device_id__scan_ranges_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/device-points/site/{site_id}/device/{device_id}/{point_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Update a device point
         * @description Update a device point. Triggers scan range recompute unless locked.
         */
        put: operations["update_point_api_device_points_site__site_id__device__device_id___point_id__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/device-points/site/{site_id}/device/{device_id}/{point_id}/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Restore a soft-deleted device point
         * @description Restore a soft-deleted device point. Triggers scan range recompute.
         */
        post: operations["restore_point_api_device_points_site__site_id__device__device_id___point_id__restore_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/devices/site/{site_id}/devices": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List all devices at a site */
        get: operations["get_all_devices_endpoint_api_devices_site__site_id__devices_get"];
        put?: never;
        /** Create a device at a site */
        post: operations["create_new_device_api_devices_site__site_id__devices_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/devices/site/{site_id}/devices/{device_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get a device by ID */
        get: operations["get_device_api_devices_site__site_id__devices__device_id__get"];
        /** Update a device */
        put: operations["update_existing_device_api_devices_site__site_id__devices__device_id__put"];
        post?: never;
        /** Soft- or hard-delete a device */
        delete: operations["delete_existing_device_api_devices_site__site_id__devices__device_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/devices/site/{site_id}/devices/{device_id}/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Restore a soft-deleted device
         * @description Restore a soft-deleted device and all its soft-deleted points under the same device_id.
         */
        post: operations["restore_existing_device_api_devices_site__site_id__devices__device_id__restore_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/health_modbus_client": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Health Modbus Client
         * @description Connects to the Modbus server and reads a single register to confirm end-to-end communication.
         */
        get: operations["health_modbus_client_api_health_modbus_client_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/healthz": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Health Check
         * @description Health check endpoint that verifies API is running.
         */
        get: operations["health_check_api_healthz_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/healthz/site/{site_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Site Devices Health
         * @description Check Modbus TCP reachability for every active device in a site.
         *
         *     For devices with read_from_aggregator=true the aggregator host/port is probed;
         *     otherwise the device's own host/port is used. All devices are checked concurrently.
         */
        get: operations["site_devices_health_api_healthz_site__site_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/healthz/site/{site_id}/device/{device_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Device Health
         * @description Check Modbus TCP reachability for a single device.
         */
        get: operations["device_health_api_healthz_site__site_id__device__device_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/modbus-live-stream-raw-registers/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Live Stream Sessions
         * @description List sessions with their configs and status.
         *
         *     - Omit `status` → all sessions with data in Redis (active + stopped within TTL)
         *     - `?status=active` → only currently polling sessions
         *     - `?status=stopped` → only sessions that have ended but whose data is still in Redis
         */
        get: operations["list_live_stream_sessions_api_modbus_live_stream_raw_registers_sessions_get"];
        put?: never;
        post?: never;
        /**
         * Delete All Live Stream Sessions
         * @description Cancel all active sessions and delete all Redis data for every session.
         */
        delete: operations["delete_all_live_stream_sessions_api_modbus_live_stream_raw_registers_sessions_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/modbus-live-stream-raw-registers/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Live Stream Raw Registers
         * @description Stream live Modbus raw register reads over Server-Sent Events.
         *
         *     Connects to the target device, polls the specified register range at the given
         *     interval, and emits SSE events until duration expires or the client disconnects.
         *
         *     Events:
         *     - connected: first event, contains session_id for use with the stop/delete endpoints
         *     - poll: one reading per interval with all register values
         *     - error: Modbus or connection error (stream continues unless unrecoverable)
         *     - done: emitted once when the session ends
         */
        post: operations["start_live_stream_raw_registers_api_modbus_live_stream_raw_registers_stream_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/modbus-live-stream-raw-registers/stream/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Delete Live Stream Raw Registers
         * @description Stop polling and delete all Redis data for this session immediately.
         */
        delete: operations["delete_live_stream_raw_registers_api_modbus_live_stream_raw_registers_stream__session_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/modbus-live-stream-raw-registers/stream/{session_id}/resume": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Resume Live Stream Raw Registers
         * @description Resume a stopped session under the same session_id. History continues accumulating.
         */
        get: operations["resume_live_stream_raw_registers_api_modbus_live_stream_raw_registers_stream__session_id__resume_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/modbus-live-stream-raw-registers/stream/{session_id}/stop": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Stop Live Stream Raw Registers
         * @description Stop polling. Redis data (session params + history) remains accessible until TTL expires.
         */
        get: operations["stop_live_stream_raw_registers_api_modbus_live_stream_raw_registers_stream__session_id__stop_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/modbus-live-stream-register-snapshot/registers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Live Stream Register Snapshot
         * @description Return the last 5 decoded register reads for a live stream session.
         *
         *     Snapshots are ordered newest-first. timestamps[j] corresponds to registers[i].values[j].
         *     Returns empty lists if no polls have been recorded yet.
         *     Returns 404 if the session is unknown or its data has expired (TTL elapsed).
         */
        get: operations["get_live_stream_register_snapshot_api_modbus_live_stream_register_snapshot_registers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/readyz": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Readiness Check
         * @description Readiness probe for Kubernetes.
         *
         *     Gates on the hard runtime dependencies — Postgres and Redis — using the
         *     lightweight shared health checks (a `SELECT 1` and a Redis PING). Returns
         *     HTTP 503 if either is unreachable so k8s stops routing traffic to the pod.
         *     Kept intentionally cheap; the detailed /db_health and /redis_health endpoints
         *     are too heavy to run on every probe interval.
         */
        get: operations["readiness_check_api_readyz_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/redis_health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Redis Health
         * @description Redis health check endpoint with detailed information.
         *
         *     Returns:
         *         Dictionary containing Redis connection status, configuration, and server information
         */
        get: operations["redis_health_api_redis_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/site-functions/site/{site_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List the endpoints a site's profile declares */
        get: operations["get_site_endpoints_api_site_functions_site__site_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/site-functions/site/{site_id}/common-energy-summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Energy (kWh) per device and in total, integrated from each device's active_power */
        get: operations["site_function_common_energy_summary_api_site_functions_site__site_id__common_energy_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/site-functions/site/{site_id}/device/{device_id}/device-inverter-availability": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Inverter availability (%): share of inverter_state samples in mppt or derating */
        get: operations["site_function_device_inverter_availability_api_site_functions_site__site_id__device__device_id__device_inverter_availability_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/site-functions/site/{site_id}/device/{device_id}/device-plant-inverter-availability": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Plant inverter availability (%): pooled over the plant controller's inv01..04_mode */
        get: operations["site_function_device_plant_inverter_availability_api_site_functions_site__site_id__device__device_id__device_plant_inverter_availability_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/site-functions/site/{site_id}/site-poi-power": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Point-of-interconnection active power series, with peak and average (kW) */
        get: operations["site_function_site_poi_power_api_site_functions_site__site_id__site_poi_power_get"];
        put?: never;
        post?: never;
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
        /** List all sites */
        get: operations["get_all_sites_endpoint_api_sites_get"];
        put?: never;
        /** Create a site */
        post: operations["create_new_site_api_sites_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sites/comprehensive/{site_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get a site with its devices and their categorized points */
        get: operations["get_comprehensive_site_endpoint_api_sites_comprehensive__site_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sites/{site_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get a site by ID */
        get: operations["get_site_api_sites__site_id__get"];
        /** Update a site */
        put: operations["update_site_endpoint_api_sites__site_id__put"];
        post?: never;
        /** Soft- or hard-delete a site */
        delete: operations["delete_site_endpoint_api_sites__site_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sites/{site_id}/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Restore a soft-deleted site
         * @description Restore a soft-deleted site, all its soft-deleted devices, and their soft-deleted points.
         */
        post: operations["restore_site_endpoint_api_sites__site_id__restore_post"];
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
         * CacheGetResponse
         * @description Response model for retrieving a value from the cache.
         */
        CacheGetResponse: {
            /**
             * Exists
             * @description Whether the key exists in the cache
             */
            exists: boolean;
            /**
             * Key
             * @description Cache key
             */
            key: string;
            /**
             * Value
             * @description Cached value, or None if the key is absent
             */
            value: unknown;
        };
        /**
         * CacheSetRequest
         * @description Request model for setting a value in the cache.
         */
        CacheSetRequest: {
            /**
             * Key
             * @description Cache key
             */
            key: string;
            /**
             * Ttl
             * @description Time-to-live in seconds; None means no expiry
             */
            ttl?: number | null;
            /**
             * Value
             * @description Value to cache
             */
            value: unknown;
        };
        /**
         * Coordinates
         * @description Coordinates model for site location.
         */
        Coordinates: {
            /**
             * Lat
             * @description Latitude
             */
            lat: number;
            /**
             * Lng
             * @description Longitude
             */
            lng: number;
        };
        /**
         * DeviceCreateRequest
         * @description Request model for creating a new device.
         */
        DeviceCreateRequest: {
            /**
             * Description
             * @description Optional device description
             */
            description?: string | null;
            /**
             * Host
             * @description Device hostname or IP address
             */
            host: string;
            /**
             * Modbus Address Mode
             * @description zero_based: use addresses as-is; one_based: subtract 1 before sending to pymodbus (for devices whose docs use 1-based numbering)
             * @default zero_based
             * @enum {string}
             */
            modbus_address_mode: "zero_based" | "one_based";
            /**
             * Model
             * @description Device model
             */
            model?: string | null;
            /**
             * Name
             * @description Unique device name/identifier
             */
            name: string;
            /**
             * Poll Enabled
             * @description Whether polling is enabled for this device
             * @default true
             */
            poll_enabled: boolean;
            /**
             * Port
             * @description Device port (default: 502)
             * @default 502
             */
            port: number;
            /**
             * Protocol
             * @description Communication protocol
             * @default Modbus
             * @enum {string}
             */
            protocol: "Modbus" | "DNP";
            /**
             * Read From Aggregator
             * @description Whether to read from edge aggregator
             * @default true
             */
            read_from_aggregator: boolean;
            /** @description Initial scan ranges (optional) */
            scan_ranges?: components["schemas"]["DeviceScanRanges"] | null;
            /**
             * Server Address
             * @description Server address (default: 1)
             * @default 1
             */
            server_address: number;
            /**
             * Timeout
             * @description Optional timeout (seconds)
             */
            timeout?: number | null;
            /**
             * Type
             * @description Device type. Case-insensitive on input; stored uppercase.
             * @enum {string}
             */
            type: "BESS" | "ES" | "INVERTER" | "PV" | "GENERATOR" | "LOADBANK" | "RELAY" | "IED" | "METER" | "RTAC";
            /**
             * Vendor
             * @description Device vendor
             */
            vendor?: string | null;
        };
        /**
         * DeviceDeleteResponse
         * @description Response model for a deleted device.
         */
        DeviceDeleteResponse: {
            /**
             * Device Id
             * @description Deleted device ID
             */
            device_id: number;
            /**
             * Mode
             * @description soft: device_id preserved and restorable; hard: permanently removed
             * @enum {string}
             */
            mode: "soft" | "hard";
            /**
             * Site Id
             * @description Site ID for the deleted device
             */
            site_id: number;
        };
        /** DeviceEnergy */
        DeviceEnergy: {
            /** Device Id */
            device_id: number;
            /** Device Name */
            device_name: string;
            /** Energy Kwh */
            energy_kwh: number;
            /**
             * Point Id
             * @description The power point that was integrated
             */
            point_id: number;
            /** Sample Count */
            sample_count: number;
        };
        /** DeviceHealthStatus */
        DeviceHealthStatus: {
            /** Device Id */
            device_id: number;
            /** Error */
            error?: string | null;
            /** Host */
            host: string;
            /** Latency Ms */
            latency_ms?: number | null;
            /** Name */
            name: string;
            /** Poll Enabled */
            poll_enabled: boolean;
            /** Port */
            port: number;
            /** Reachable */
            reachable: boolean;
            /** Read From Aggregator */
            read_from_aggregator: boolean;
        };
        /**
         * DevicePointCreateRequest
         * @description Request model for creating a device point directly (Config-free).
         */
        DevicePointCreateRequest: {
            /** Address */
            address?: number | null;
            /** Bitfield Detail */
            bitfield_detail?: {
                [key: string]: string;
            } | null;
            /**
             * Byte Order
             * @default big-endian
             */
            byte_order: string;
            /**
             * Category
             * @default NATIVE
             * @enum {string}
             */
            category: "NATIVE" | "STANDARDIZED" | "VIRTUAL";
            /**
             * Class
             * @description Signal class: ANALOG (metered/continuous), BINARY (state/status/flags), ALARM (warning/fault/error/trip), CONTROL (setpoint/command/config)
             */
            class?: ("ANALOG" | "BINARY" | "ALARM" | "CONTROL") | null;
            /**
             * Data Type
             * @description Register interpretation. Width is encoded in the type (e.g. enum32, bitfield16); `size` must match register_size(data_type).
             * @enum {string}
             */
            data_type: "bool" | "uint16" | "int16" | "uint32" | "int32" | "uint64" | "int64" | "float32" | "float64" | "raw" | "enum16" | "enum32" | "bitfield16" | "bitfield32" | "status_word16" | "status_word32";
            /** Enum Detail */
            enum_detail?: {
                [key: string]: string;
            } | null;
            /** Name */
            name: string;
            /** Poll Kind */
            poll_kind?: ("holding" | "input" | "coils") | null;
            /** Scale Factor */
            scale_factor?: number | null;
            /**
             * Severity
             * @description Severity: HIGH, MEDIUM or LOW
             */
            severity?: ("HIGH" | "MEDIUM" | "LOW") | null;
            /** Size */
            size: number;
            /** Unit */
            unit?: string | null;
            /**
             * Word Order
             * @default msw_first
             */
            word_order: string;
        };
        /**
         * DevicePointResponse
         * @description Response model for a device point.
         */
        DevicePointResponse: {
            /**
             * Address
             * @description Point address
             */
            address: number;
            /**
             * Bitfield Detail
             * @description Bitfield detail mapping
             */
            bitfield_detail?: {
                [key: string]: string;
            } | null;
            /**
             * Byte Order
             * @description Byte order for interpretation
             * @default big-endian
             */
            byte_order: string;
            /**
             * Category
             * @description Point category: NATIVE, STANDARDIZED, or VIRTUAL
             * @default NATIVE
             */
            category: string;
            /**
             * Class
             * @description Signal class: ANALOG (metered/continuous), BINARY (state/status/flags), ALARM (warning/fault/error/trip), CONTROL (setpoint/command/config)
             */
            class?: ("ANALOG" | "BINARY" | "ALARM" | "CONTROL") | null;
            /**
             * Data Type
             * @description Data type
             */
            data_type: string;
            /**
             * Deleted At
             * @description Soft-delete timestamp; null means active
             */
            deleted_at?: string | null;
            /**
             * Device Id
             * @description Device ID
             */
            device_id: number;
            /**
             * Enum Detail
             * @description Enum detail mapping
             */
            enum_detail?: {
                [key: string]: string;
            } | null;
            /**
             * Id
             * @description Primary key
             */
            id: number;
            /**
             * Name
             * @description Point name
             */
            name: string;
            /**
             * Poll Kind
             * @description Register type: holding, input, or coils
             */
            poll_kind?: string | null;
            /**
             * Scale Factor
             * @description Scale factor
             */
            scale_factor?: number | null;
            /**
             * Severity
             * @description Severity: HIGH, MEDIUM or LOW
             */
            severity?: ("HIGH" | "MEDIUM" | "LOW") | null;
            /**
             * Site Id
             * @description Site ID
             */
            site_id: number;
            /**
             * Size
             * @description Point size
             */
            size: number;
            /**
             * Unit
             * @description Unit
             */
            unit?: string | null;
            /**
             * Word Order
             * @description Word order for multi-register types
             * @default msw_first
             */
            word_order: string;
        };
        /**
         * DevicePointUpdateRequest
         * @description Request model for updating a device point.
         */
        DevicePointUpdateRequest: {
            /** Address */
            address?: number | null;
            /** Bitfield Detail */
            bitfield_detail?: {
                [key: string]: string;
            } | null;
            /** Byte Order */
            byte_order?: string | null;
            /**
             * Class
             * @description Signal class: ANALOG (metered/continuous), BINARY (state/status/flags), ALARM (warning/fault/error/trip), CONTROL (setpoint/command/config)
             */
            class?: ("ANALOG" | "BINARY" | "ALARM" | "CONTROL") | null;
            /**
             * Data Type
             * @description Register interpretation. Width is encoded in the type (e.g. enum32, bitfield16); `size` must match register_size(data_type).
             */
            data_type?: ("bool" | "uint16" | "int16" | "uint32" | "int32" | "uint64" | "int64" | "float32" | "float64" | "raw" | "enum16" | "enum32" | "bitfield16" | "bitfield32" | "status_word16" | "status_word32") | null;
            /** Enum Detail */
            enum_detail?: {
                [key: string]: string;
            } | null;
            /** Name */
            name?: string | null;
            /** Poll Kind */
            poll_kind?: ("holding" | "input" | "coils") | null;
            /** Scale Factor */
            scale_factor?: number | null;
            /**
             * Severity
             * @description Severity: HIGH, MEDIUM or LOW
             */
            severity?: ("HIGH" | "MEDIUM" | "LOW") | null;
            /** Size */
            size?: number | null;
            /** Unit */
            unit?: string | null;
            /** Word Order */
            word_order?: string | null;
        };
        /**
         * DevicePointsBulkRequest
         * @description Bulk upsert: create new points and update existing ones (matched by name) in one call.
         */
        DevicePointsBulkRequest: {
            /** Points */
            points: components["schemas"]["DevicePointCreateRequest"][];
        };
        /**
         * DevicePointsCategoryGrouped
         * @description Device points grouped by category.
         */
        DevicePointsCategoryGrouped: {
            /** Native */
            native?: components["schemas"]["DevicePointResponse"][];
            /** Standardized */
            standardized?: components["schemas"]["DevicePointResponse"][];
            /** Virtual */
            virtual?: components["schemas"]["DevicePointResponse"][];
        };
        /**
         * DeviceScanRanges
         * @description Scan ranges categorized by register type.
         */
        DeviceScanRanges: {
            /** Coils */
            coils?: components["schemas"]["RegisterRange"][];
            /** Holding */
            holding?: components["schemas"]["RegisterRange"][];
            /** Input */
            input?: components["schemas"]["RegisterRange"][];
        };
        /**
         * DeviceUpdate
         * @description Request model for updating a device.
         */
        DeviceUpdate: {
            /**
             * Description
             * @description Device description
             */
            description?: string | null;
            /**
             * Host
             * @description Device hostname or IP address
             */
            host?: string | null;
            /**
             * Modbus Address Mode
             * @description zero_based: use addresses as-is; one_based: subtract 1 before sending to pymodbus
             */
            modbus_address_mode?: ("zero_based" | "one_based") | null;
            /**
             * Model
             * @description Device model
             */
            model?: string | null;
            /**
             * Name
             * @description Device name/identifier
             */
            name?: string | null;
            /**
             * Poll Enabled
             * @description Whether polling is enabled for this device
             */
            poll_enabled?: boolean | null;
            /**
             * Port
             * @description Device port
             */
            port?: number | null;
            /**
             * Protocol
             * @description Communication protocol
             */
            protocol?: ("Modbus" | "DNP") | null;
            /**
             * Read From Aggregator
             * @description Whether to read from edge aggregator
             */
            read_from_aggregator?: boolean | null;
            /** @description Updated scan ranges (does not lock) */
            scan_ranges?: components["schemas"]["DeviceScanRanges"] | null;
            /**
             * Server Address
             * @description Server address
             */
            server_address?: number | null;
            /**
             * Timeout
             * @description Optional timeout (seconds)
             */
            timeout?: number | null;
            /**
             * Type
             * @description Device type. Case-insensitive on input; stored uppercase.
             */
            type?: ("BESS" | "ES" | "INVERTER" | "PV" | "GENERATOR" | "LOADBANK" | "RELAY" | "IED" | "METER" | "RTAC") | null;
            /**
             * Vendor
             * @description Device vendor
             */
            vendor?: string | null;
        };
        /**
         * DeviceWithPoints
         * @description Device response with its device points grouped by category.
         */
        DeviceWithPoints: {
            /**
             * Created At
             * Format: date-time
             * @description Timestamp when device was created
             */
            created_at: string;
            /**
             * Deleted At
             * @description Soft-delete timestamp; null means active
             */
            deleted_at?: string | null;
            /**
             * Description
             * @description Device description
             */
            description?: string | null;
            /**
             * Device Id
             * @description Device ID
             */
            device_id: number;
            /**
             * Host
             * @description Device hostname or IP address
             */
            host: string;
            /**
             * Modbus Address Mode
             * @description zero_based or one_based — controls pymodbus address offset
             * @default zero_based
             */
            modbus_address_mode: string;
            /**
             * Model
             * @description Device model
             */
            model?: string | null;
            /**
             * Name
             * @description Device name
             */
            name: string;
            points?: components["schemas"]["DevicePointsCategoryGrouped"];
            /**
             * Poll Enabled
             * @description Whether polling is enabled for this device
             * @default true
             */
            poll_enabled: boolean;
            /**
             * Port
             * @description Device port
             */
            port: number;
            /**
             * Protocol
             * @description Communication protocol
             */
            protocol: string;
            /**
             * Read From Aggregator
             * @description Whether to read from edge aggregator
             * @default true
             */
            read_from_aggregator: boolean;
            /** @description Auto-computed or manually locked scan ranges */
            scan_ranges?: components["schemas"]["DeviceScanRanges"] | null;
            /**
             * Scan Ranges Locked
             * @description Whether scan ranges are locked against auto-recompute
             * @default false
             */
            scan_ranges_locked: boolean;
            /**
             * Server Address
             * @description Server address
             */
            server_address: number;
            /**
             * Site Id
             * @description Site ID (4-digit number)
             */
            site_id: number;
            /**
             * Timeout
             * @description Optional timeout (seconds)
             */
            timeout?: number | null;
            /**
             * Type
             * @description Device type
             */
            type: string;
            /**
             * Updated At
             * Format: date-time
             * @description Timestamp when device was last updated
             */
            updated_at: string;
            /**
             * Vendor
             * @description Device vendor
             */
            vendor?: string | null;
        };
        /** EnergySummaryResult */
        EnergySummaryResult: {
            /** Devices */
            devices?: components["schemas"]["DeviceEnergy"][];
            /**
             * End Time
             * Format: date-time
             */
            end_time: string;
            /**
             * Energy Kwh
             * @description Sum over devices
             */
            energy_kwh: number;
            /** Site Id */
            site_id: number;
            /**
             * Start Time
             * Format: date-time
             */
            start_time: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * HealthResponse
         * @description Response model for health check.
         */
        HealthResponse: {
            /** Detail */
            detail?: string | null;
            /**
             * Device Id
             * @description Modbus unit/slave ID
             */
            device_id: number;
            /** Host */
            host: string;
            /** Ok */
            ok: boolean;
            /** Port */
            port: number;
        };
        /** InverterAvailabilityResult */
        InverterAvailabilityResult: {
            /**
             * Availability Pct
             * @description online / total samples x 100; null if no readings
             */
            availability_pct?: number | null;
            /** Device Id */
            device_id: number;
            /** Device Name */
            device_name: string;
            /**
             * End Time
             * Format: date-time
             */
            end_time: string;
            /** Online Sample Count */
            online_sample_count: number;
            /**
             * Online States
             * @description State codes counted as available
             */
            online_states: number[];
            /** Sample Count */
            sample_count: number;
            /** Site Id */
            site_id: number;
            /**
             * Start Time
             * Format: date-time
             */
            start_time: string;
            /**
             * State Points
             * @description The state points that were evaluated
             */
            state_points: string[];
        };
        /** LatestMeta */
        LatestMeta: {
            /** Device Id */
            device_id: number;
            /** Point Ids */
            point_ids?: number[] | null;
            /** Site Id */
            site_id: number;
            /** Total Count */
            total_count: number;
        };
        /** LatestResponse */
        LatestResponse: {
            meta: components["schemas"]["LatestMeta"];
            /** Readings */
            readings: {
                [key: string]: components["schemas"]["PointLatest"];
            };
        };
        /** LiveStreamDeleteAllSessionsResponse */
        LiveStreamDeleteAllSessionsResponse: {
            /** Cancelled Active Sessions */
            cancelled_active_sessions: number;
            /** Deleted Count */
            deleted_count: number;
            /** Deleted Sessions */
            deleted_sessions: string[];
        };
        /** LiveStreamDeleteSessionResponse */
        LiveStreamDeleteSessionResponse: {
            /** Deleted */
            deleted: string;
        };
        /** LiveStreamRawRegistersParams */
        LiveStreamRawRegistersParams: {
            /**
             * Byte Order
             * @default big
             * @enum {string}
             */
            byte_order: "big" | "little";
            /**
             * Duration
             * @description Session length in seconds, max 1 hour
             * @default 3600
             */
            duration: number;
            /** End Address */
            end_address: number;
            /**
             * Host
             * @description Modbus device IP/hostname
             */
            host: string;
            /**
             * Interval
             * @description Seconds between polls
             * @default 1
             */
            interval: number;
            /**
             * Kind
             * @default holding
             * @enum {string}
             */
            kind: "holding" | "input";
            /**
             * Modbus Address Mode
             * @description zero_based: address sent as-is; one_based: subtract 1 before sending to device
             * @default zero_based
             * @enum {string}
             */
            modbus_address_mode: "zero_based" | "one_based";
            /**
             * Port
             * @default 502
             */
            port: number;
            /**
             * Register Configs
             * @description Optional per-address config, e.g. {"1400": {"label": "voltage", "data_type": "float32"}}
             */
            register_configs?: {
                [key: string]: components["schemas"]["LiveStreamRawRegistersRegisterConfig"];
            } | null;
            /**
             * Server Address
             * @description Modbus unit/slave ID
             * @default 1
             */
            server_address: number;
            /** Start Address */
            start_address: number;
            /**
             * Word Order
             * @default msw_first
             * @enum {string}
             */
            word_order: "msw_first" | "lsw_first";
        };
        /** LiveStreamRawRegistersRegisterConfig */
        LiveStreamRawRegistersRegisterConfig: {
            /** Byte Order */
            byte_order?: ("big" | "little") | null;
            /**
             * Data Type
             * @default int16
             * @enum {string}
             */
            data_type: "bool" | "uint16" | "int16" | "uint32" | "int32" | "uint64" | "int64" | "float32" | "float64" | "raw";
            /** Label */
            label?: string | null;
            /** Word Order */
            word_order?: ("msw_first" | "lsw_first") | null;
        };
        /** LiveStreamRegisterSnapshotEntry */
        LiveStreamRegisterSnapshotEntry: {
            /** Address */
            address: number;
            /**
             * Data Type
             * @default int16
             */
            data_type: string;
            /**
             * Label
             * @default unknown
             */
            label: string;
            /** Values */
            values: (number | null)[];
        };
        /** LiveStreamRegisterSnapshotResponse */
        LiveStreamRegisterSnapshotResponse: {
            /** Registers */
            registers: components["schemas"]["LiveStreamRegisterSnapshotEntry"][];
            /** Timestamps */
            timestamps: string[];
        };
        /** LiveStreamSessionInfo */
        LiveStreamSessionInfo: {
            /** Duration */
            duration: number;
            /** End Address */
            end_address: number;
            /** Host */
            host: string;
            /** Interval */
            interval: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "holding" | "input";
            /** Modbus Address Mode */
            modbus_address_mode: string;
            /** Port */
            port: number;
            /** Server Address */
            server_address: number;
            /** Session Id */
            session_id: string;
            /** Start Address */
            start_address: number;
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "stopped";
        };
        /** LiveStreamSessionsResponse */
        LiveStreamSessionsResponse: {
            /** Sessions */
            sessions: components["schemas"]["LiveStreamSessionInfo"][];
        };
        /** LiveStreamStopSessionResponse */
        LiveStreamStopSessionResponse: {
            /** Stopped */
            stopped: string;
        };
        /**
         * Location
         * @description Location model for site address details.
         */
        Location: {
            /**
             * City
             * @description City
             */
            city: string;
            /**
             * State
             * @description State/province
             */
            state: string;
            /**
             * Street
             * @description Street address
             */
            street: string;
            /**
             * Zip Code
             * @description Zip/postal code
             */
            zip_code: number;
        };
        /** PoiPowerResult */
        PoiPowerResult: {
            /**
             * Average Kw
             * @description Mean of the samples in the window; null if no readings
             */
            average_kw?: number | null;
            /**
             * End Time
             * Format: date-time
             */
            end_time: string;
            /**
             * Peak Kw
             * @description Highest POI active power in the window; null if no readings
             */
            peak_kw?: number | null;
            /** @description POI active power samples, oldest first */
            series: components["schemas"]["PointTimeseries"];
            /** Site Id */
            site_id: number;
            /**
             * Start Time
             * Format: date-time
             */
            start_time: string;
        };
        /** PointLatest */
        PointLatest: {
            /** Class */
            class?: ("ANALOG" | "BINARY" | "ALARM" | "CONTROL") | null;
            /** Data Type */
            data_type: string;
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Severity */
            severity?: ("HIGH" | "MEDIUM" | "LOW") | null;
            /** Time */
            time?: string | null;
            /** Translated Value */
            translated_value?: string | {
                [key: string]: number;
            } | null;
            /** Unit */
            unit?: string | null;
            /** Value */
            value?: number | null;
        };
        /** PointTimeseries */
        PointTimeseries: {
            /** Bit Labels */
            bit_labels?: string[] | null;
            /** Class */
            class?: ("ANALOG" | "BINARY" | "ALARM" | "CONTROL") | null;
            /**
             * Count
             * @default 0
             */
            count: number;
            /** Data Type */
            data_type: string;
            /** Enum Map */
            enum_map?: {
                [key: string]: string;
            } | null;
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Severity */
            severity?: ("HIGH" | "MEDIUM" | "LOW") | null;
            /** Timeseries */
            timeseries?: components["schemas"]["TimeseriesPoint"][];
            /** Unit */
            unit?: string | null;
        };
        /**
         * RegisterRange
         * @description A single Modbus read window.
         */
        RegisterRange: {
            /** Count */
            count: number;
            /** Start Index */
            start_index: number;
        };
        /**
         * SiteComprehensiveResponse
         * @description Comprehensive site response with devices and their categorized points.
         */
        SiteComprehensiveResponse: {
            /**
             * Capacity
             * @description Site capacity
             */
            capacity: string;
            /**
             * Client Id
             * @description Client identifier
             */
            client_id: string;
            /** @description Geographic coordinates */
            coordinates?: components["schemas"]["Coordinates"] | null;
            /**
             * Created At
             * Format: date-time
             * @description Timestamp when site was created
             */
            created_at: string;
            /**
             * Description
             * @description Site description
             */
            description?: string | null;
            /**
             * Device Count
             * @description Number of devices at this site
             */
            device_count: number;
            /**
             * Devices
             * @description Devices with categorized points
             */
            devices?: components["schemas"]["DeviceWithPoints"][];
            /**
             * Last Update
             * Format: date-time
             * @description Timestamp of last update
             */
            last_update: string;
            /** @description Site location details */
            location?: components["schemas"]["Location"] | null;
            /**
             * Name
             * @description Site name
             */
            name: string;
            /**
             * Operator
             * @description Site operator
             */
            operator: string;
            /**
             * Site Id
             * @description Site ID (4-digit number)
             */
            site_id: number;
            /**
             * Updated At
             * Format: date-time
             * @description Timestamp when site was last updated
             */
            updated_at: string;
        };
        /**
         * SiteCreateRequest
         * @description Request model for creating a new site.
         */
        SiteCreateRequest: {
            /**
             * Capacity
             * @description Site capacity
             */
            capacity: string;
            /**
             * Client Id
             * @description Client identifier
             */
            client_id: string;
            /** @description Geographic coordinates */
            coordinates?: components["schemas"]["Coordinates"] | null;
            /**
             * Description
             * @description Optional site description
             */
            description?: string | null;
            /** @description Site location details */
            location: components["schemas"]["Location"];
            /**
             * Name
             * @description Site name
             */
            name: string;
            /**
             * Operator
             * @description Site operator
             */
            operator: string;
            /**
             * Profile
             * @description Site profile key selecting the site's endpoints (e.g. 'alpha_solar'); omit to use 'default', which offers only the common endpoints
             */
            profile?: string | null;
        };
        /**
         * SiteDeleteResponse
         * @description Response model for a deleted site.
         */
        SiteDeleteResponse: {
            /**
             * Mode
             * @description soft: site_id preserved and restorable; hard: permanently removed
             * @enum {string}
             */
            mode: "soft" | "hard";
            /**
             * Site Id
             * @description Deleted site ID
             */
            site_id: number;
        };
        /** SiteDevicesHealthResponse */
        SiteDevicesHealthResponse: {
            /** Devices */
            devices: components["schemas"]["DeviceHealthStatus"][];
            /** Reachable */
            reachable: number;
            /** Site Id */
            site_id: number;
            /** Total */
            total: number;
            /** Unreachable */
            unreachable: number;
        };
        /** SiteEndpointInfo */
        SiteEndpointInfo: {
            /**
             * Kind
             * @description common/site: /site/{site_id}/{name}; device: /site/{site_id}/device/{device_id}/{name}
             * @enum {string}
             */
            kind: "common" | "site" | "device";
            /**
             * Method
             * @constant
             */
            method: "GET";
            /**
             * Name
             * @description Function name, the last URL segment; starts with its kind
             */
            name: string;
            /** Summary */
            summary: string;
        };
        /** SiteEndpointsResponse */
        SiteEndpointsResponse: {
            /**
             * Endpoints
             * @description Endpoints declared in the site's profile.py
             */
            endpoints?: components["schemas"]["SiteEndpointInfo"][];
            /**
             * Profile
             * @description The site's profile key
             */
            profile: string;
            /** Site Id */
            site_id: number;
        };
        /**
         * SiteResponse
         * @description Response model for site data.
         */
        SiteResponse: {
            /**
             * Capacity
             * @description Site capacity
             */
            capacity: string;
            /**
             * Client Id
             * @description Client identifier
             */
            client_id: string;
            /** @description Geographic coordinates */
            coordinates?: components["schemas"]["Coordinates"] | null;
            /**
             * Created At
             * Format: date-time
             * @description Timestamp when site was created
             */
            created_at: string;
            /**
             * Deleted At
             * @description Soft-delete timestamp; null means active
             */
            deleted_at?: string | null;
            /**
             * Description
             * @description Site description
             */
            description?: string | null;
            /**
             * Device Count
             * @description Number of devices at this site
             */
            device_count: number;
            /**
             * Last Update
             * Format: date-time
             * @description Timestamp of last update
             */
            last_update: string;
            /** @description Site location details */
            location?: components["schemas"]["Location"] | null;
            /**
             * Name
             * @description Site name
             */
            name: string;
            /**
             * Operator
             * @description Site operator
             */
            operator: string;
            /**
             * Profile
             * @description Site profile key selecting the site's endpoints; 'default' offers only the common endpoints
             */
            profile: string;
            /**
             * Site Id
             * @description Site ID (4-digit number)
             */
            site_id: number;
            /**
             * Updated At
             * Format: date-time
             * @description Timestamp when site was last updated
             */
            updated_at: string;
        };
        /**
         * SiteUpdateRequest
         * @description Request model for updating a site.
         */
        SiteUpdateRequest: {
            /**
             * Capacity
             * @description Site capacity
             */
            capacity?: string | null;
            /**
             * Client Id
             * @description Client identifier
             */
            client_id?: string | null;
            /** @description Geographic coordinates */
            coordinates?: components["schemas"]["Coordinates"] | null;
            /**
             * Description
             * @description Site description
             */
            description?: string | null;
            /** @description Site location details */
            location?: components["schemas"]["Location"] | null;
            /**
             * Name
             * @description Site name
             */
            name?: string | null;
            /**
             * Operator
             * @description Site operator
             */
            operator?: string | null;
            /**
             * Profile
             * @description Site profile key selecting the site's endpoints (e.g. 'alpha_solar'); omit to keep the current one
             */
            profile?: string | null;
        };
        /** TimeseriesMeta */
        TimeseriesMeta: {
            /** Device Id */
            device_id: number;
            /** End Time */
            end_time?: string | null;
            /** Point Ids */
            point_ids?: number[] | null;
            /** Site Id */
            site_id: number;
            /** Start Time */
            start_time?: string | null;
            /** Total Count */
            total_count: number;
        };
        /** TimeseriesPoint */
        TimeseriesPoint: {
            /**
             * Time
             * Format: date-time
             */
            time: string;
            /** Translated Value */
            translated_value?: string | {
                [key: string]: number;
            } | null;
            /** Value */
            value?: number | null;
        };
        /** TimeseriesResponse */
        TimeseriesResponse: {
            meta: components["schemas"]["TimeseriesMeta"];
            /** Readings */
            readings: {
                [key: string]: components["schemas"]["PointTimeseries"];
            };
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
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    cache_clear_all_api_cache_clear_delete: {
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
                    "application/json": unknown;
                };
            };
        };
    };
    cache_delete_api_cache_delete__key__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                key: string;
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
                    "application/json": unknown;
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
    cache_exists_api_cache_exists__key__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                key: string;
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
                    "application/json": unknown;
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
    cache_get_api_cache_get__key__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                key: string;
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
                    "application/json": components["schemas"]["CacheGetResponse"];
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
    cache_health_api_cache_health_get: {
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
                    "application/json": unknown;
                };
            };
        };
    };
    cache_list_keys_api_cache_keys_get: {
        parameters: {
            query?: {
                pattern?: string | null;
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
                    "application/json": unknown;
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
    cache_set_api_cache_set_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CacheSetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
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
    export_raw_register_map_csv_api_csv_exports_raw_register_map_csv_get: {
        parameters: {
            query: {
                /** @description Export type (e.g., 'modbus') */
                type: string;
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
                    "application/json": unknown;
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
    db_health_api_db_health_get: {
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
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_latest_readings_api_device_point_readings_site__site_id__device__device_id__latest_get: {
        parameters: {
            query?: {
                /** @description Comma-separated device_point_ids (e.g. '1,2,3'). If omitted, returns all points for the device. */
                point_ids?: string | null;
                /** @description Translate enum/bitfield values to human-readable form */
                translate?: boolean;
                /** @description IANA timezone, e.g. 'America/Los_Angeles', or a US shorthand such as 'PT'/'PDT'. Interprets naive start_time/end_time and renders response timestamps in this zone. An explicit offset on a timestamp takes precedence over this. */
                tz?: string | null;
            };
            header?: never;
            path: {
                site_id: number;
                device_id: number;
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
                    "application/json": components["schemas"]["LatestResponse"];
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
    get_timeseries_readings_api_device_point_readings_timeseries_site__site_id__device__device_id__get: {
        parameters: {
            query?: {
                /** @description Comma-separated device_point_ids (e.g. '1,2,3'). If omitted, returns all points for the device. */
                point_ids?: string | null;
                /** @description Start time in ISO format. Must carry a UTC offset (e.g. '2025-01-18T08:00:00Z' or '2025-01-18T00:00:00-08:00') unless tz is supplied. Cannot be combined with time_range. */
                start_time?: string | null;
                /** @description End time in ISO format. Must carry a UTC offset unless tz is supplied. Cannot be combined with time_range. */
                end_time?: string | null;
                /** @description Relative time window ending now: 1H, 6H, 12H, 1D, 2D, 3D, 1W, 1M, 3M. Cannot be combined with start_time/end_time. */
                time_range?: ("1H" | "6H" | "12H" | "1D" | "2D" | "3D" | "1W" | "1M" | "3M") | null;
                /** @description Maximum readings per point, taking the most recent N (returned newest-first) */
                limit?: number;
                /** @description Translate enum/bitfield values to human-readable form */
                translate?: boolean;
                /** @description IANA timezone, e.g. 'America/Los_Angeles', or a US shorthand such as 'PT'/'PDT'. Interprets naive start_time/end_time and renders response timestamps in this zone. An explicit offset on a timestamp takes precedence over this. */
                tz?: string | null;
            };
            header?: never;
            path: {
                site_id: number;
                device_id: number;
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
                    "application/json": components["schemas"]["TimeseriesResponse"];
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
    get_points_for_device_api_device_points_site__site_id__device__device_id__get: {
        parameters: {
            query?: {
                /** @description Filter points by category */
                category?: ("NATIVE" | "STANDARDIZED" | "VIRTUAL") | null;
                /** @description Include soft-deleted points */
                include_deleted?: boolean;
                /** @description Filter points by signal class: ANALOG, BINARY, ALARM or CONTROL */
                class?: ("ANALOG" | "BINARY" | "ALARM" | "CONTROL") | null;
                /** @description Filter points by severity: HIGH, MEDIUM or LOW */
                severity?: ("HIGH" | "MEDIUM" | "LOW") | null;
            };
            header?: never;
            path: {
                site_id: number;
                device_id: number;
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
                    "application/json": components["schemas"]["DevicePointResponse"][];
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
    delete_points_api_device_points_site__site_id__device__device_id__delete: {
        parameters: {
            query: {
                /** @description Point IDs to delete, e.g. ?point_ids=1&point_ids=2 */
                point_ids: number[];
                /** @description soft=preserve readings, hard=cascade delete */
                mode?: "soft" | "hard";
                /** @description Required for mode=hard */
                confirm?: boolean;
            };
            header?: never;
            path: {
                site_id: number;
                device_id: number;
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
                    "application/json": components["schemas"]["DevicePointResponse"][];
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
    bulk_upsert_points_api_device_points_site__site_id__device__device_id__bulk_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                device_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DevicePointsBulkRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DevicePointResponse"][];
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
    get_deleted_points_for_device_api_device_points_site__site_id__device__device_id__deleted_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                device_id: number;
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
                    "application/json": components["schemas"]["DevicePointResponse"][];
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
    override_scan_ranges_api_device_points_site__site_id__device__device_id__scan_ranges_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                device_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeviceScanRanges"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeviceScanRanges"];
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
    reset_scan_ranges_api_device_points_site__site_id__device__device_id__scan_ranges_delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                device_id: number;
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
                    "application/json": components["schemas"]["DeviceScanRanges"];
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
    update_point_api_device_points_site__site_id__device__device_id___point_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                device_id: number;
                point_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DevicePointUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DevicePointResponse"];
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
    restore_point_api_device_points_site__site_id__device__device_id___point_id__restore_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                device_id: number;
                point_id: number;
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
                    "application/json": components["schemas"]["DevicePointResponse"];
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
    get_all_devices_endpoint_api_devices_site__site_id__devices_get: {
        parameters: {
            query?: {
                /** @description Include soft-deleted devices */
                include_deleted?: boolean;
            };
            header?: never;
            path: {
                site_id: number;
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
                    "application/json": components["schemas"]["DeviceWithPoints"][];
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
    create_new_device_api_devices_site__site_id__devices_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeviceCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeviceWithPoints"];
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
    get_device_api_devices_site__site_id__devices__device_id__get: {
        parameters: {
            query?: {
                /** @description Return the device even if soft-deleted */
                include_deleted?: boolean;
            };
            header?: never;
            path: {
                site_id: number;
                device_id: number;
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
                    "application/json": components["schemas"]["DeviceWithPoints"];
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
    update_existing_device_api_devices_site__site_id__devices__device_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                device_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeviceUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeviceWithPoints"];
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
    delete_existing_device_api_devices_site__site_id__devices__device_id__delete: {
        parameters: {
            query?: {
                /** @description soft: preserves device_id — restorable via /restore. hard: permanent deletion, requires confirm=true. */
                mode?: "soft" | "hard";
                /** @description Must be true to execute a hard delete */
                confirm?: boolean;
            };
            header?: never;
            path: {
                site_id: number;
                device_id: number;
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
                    "application/json": components["schemas"]["DeviceDeleteResponse"];
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
    restore_existing_device_api_devices_site__site_id__devices__device_id__restore_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                device_id: number;
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
                    "application/json": components["schemas"]["DeviceWithPoints"];
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
    health_modbus_client_api_health_modbus_client_get: {
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
    health_check_api_healthz_get: {
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
    site_devices_health_api_healthz_site__site_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
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
                    "application/json": components["schemas"]["SiteDevicesHealthResponse"];
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
    device_health_api_healthz_site__site_id__device__device_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                device_id: number;
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
                    "application/json": components["schemas"]["DeviceHealthStatus"];
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
    list_live_stream_sessions_api_modbus_live_stream_raw_registers_sessions_get: {
        parameters: {
            query?: {
                /** @description Filter by status. Omit to return all. */
                status?: ("active" | "stopped") | null;
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
                    "application/json": components["schemas"]["LiveStreamSessionsResponse"];
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
    delete_all_live_stream_sessions_api_modbus_live_stream_raw_registers_sessions_delete: {
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
                    "application/json": components["schemas"]["LiveStreamDeleteAllSessionsResponse"];
                };
            };
        };
    };
    start_live_stream_raw_registers_api_modbus_live_stream_raw_registers_stream_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LiveStreamRawRegistersParams"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
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
    delete_live_stream_raw_registers_api_modbus_live_stream_raw_registers_stream__session_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
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
                    "application/json": components["schemas"]["LiveStreamDeleteSessionResponse"];
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
    resume_live_stream_raw_registers_api_modbus_live_stream_raw_registers_stream__session_id__resume_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
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
                content?: never;
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
    stop_live_stream_raw_registers_api_modbus_live_stream_raw_registers_stream__session_id__stop_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
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
                    "application/json": components["schemas"]["LiveStreamStopSessionResponse"];
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
    get_live_stream_register_snapshot_api_modbus_live_stream_register_snapshot_registers_get: {
        parameters: {
            query: {
                /** @description session_id from the connected SSE event */
                session_id: string;
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
                    "application/json": components["schemas"]["LiveStreamRegisterSnapshotResponse"];
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
    readiness_check_api_readyz_get: {
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
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    redis_health_api_redis_health_get: {
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
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_site_endpoints_api_site_functions_site__site_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
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
                    "application/json": components["schemas"]["SiteEndpointsResponse"];
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
    site_function_common_energy_summary_api_site_functions_site__site_id__common_energy_summary_get: {
        parameters: {
            query?: {
                /** @description Window start (ISO 8601 with a UTC offset, or naive with tz). Cannot be combined with time_range. */
                start_time?: string | null;
                /** @description Window end; defaults to now. Needs start_time. Cannot be combined with time_range. */
                end_time?: string | null;
                /** @description Relative window ending now: 1H, 6H, 12H, 1D, 2D, 3D, 1W, 1M, 3M. */
                time_range?: ("1H" | "6H" | "12H" | "1D" | "2D" | "3D" | "1W" | "1M" | "3M") | null;
                /** @description IANA timezone (or US shorthand such as 'PT') for naive bounds and for response timestamps. */
                tz?: string | null;
            };
            header?: never;
            path: {
                site_id: number;
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
                    "application/json": components["schemas"]["EnergySummaryResult"];
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
    site_function_device_inverter_availability_api_site_functions_site__site_id__device__device_id__device_inverter_availability_get: {
        parameters: {
            query?: {
                /** @description Window start (ISO 8601 with a UTC offset, or naive with tz). Cannot be combined with time_range. */
                start_time?: string | null;
                /** @description Window end; defaults to now. Needs start_time. Cannot be combined with time_range. */
                end_time?: string | null;
                /** @description Relative window ending now: 1H, 6H, 12H, 1D, 2D, 3D, 1W, 1M, 3M. */
                time_range?: ("1H" | "6H" | "12H" | "1D" | "2D" | "3D" | "1W" | "1M" | "3M") | null;
                /** @description IANA timezone (or US shorthand such as 'PT') for naive bounds and for response timestamps. */
                tz?: string | null;
            };
            header?: never;
            path: {
                site_id: number;
                device_id: number;
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
                    "application/json": components["schemas"]["InverterAvailabilityResult"];
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
    site_function_device_plant_inverter_availability_api_site_functions_site__site_id__device__device_id__device_plant_inverter_availability_get: {
        parameters: {
            query?: {
                /** @description Window start (ISO 8601 with a UTC offset, or naive with tz). Cannot be combined with time_range. */
                start_time?: string | null;
                /** @description Window end; defaults to now. Needs start_time. Cannot be combined with time_range. */
                end_time?: string | null;
                /** @description Relative window ending now: 1H, 6H, 12H, 1D, 2D, 3D, 1W, 1M, 3M. */
                time_range?: ("1H" | "6H" | "12H" | "1D" | "2D" | "3D" | "1W" | "1M" | "3M") | null;
                /** @description IANA timezone (or US shorthand such as 'PT') for naive bounds and for response timestamps. */
                tz?: string | null;
            };
            header?: never;
            path: {
                site_id: number;
                device_id: number;
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
                    "application/json": components["schemas"]["InverterAvailabilityResult"];
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
    site_function_site_poi_power_api_site_functions_site__site_id__site_poi_power_get: {
        parameters: {
            query?: {
                /** @description Window start (ISO 8601 with a UTC offset, or naive with tz). Cannot be combined with time_range. */
                start_time?: string | null;
                /** @description Window end; defaults to now. Needs start_time. Cannot be combined with time_range. */
                end_time?: string | null;
                /** @description Relative window ending now: 1H, 6H, 12H, 1D, 2D, 3D, 1W, 1M, 3M. */
                time_range?: ("1H" | "6H" | "12H" | "1D" | "2D" | "3D" | "1W" | "1M" | "3M") | null;
                /** @description IANA timezone (or US shorthand such as 'PT') for naive bounds and for response timestamps. */
                tz?: string | null;
            };
            header?: never;
            path: {
                site_id: number;
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
                    "application/json": components["schemas"]["PoiPowerResult"];
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
    get_all_sites_endpoint_api_sites_get: {
        parameters: {
            query?: {
                /** @description Include soft-deleted sites */
                include_deleted?: boolean;
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
                    "application/json": components["schemas"]["SiteResponse"][];
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
    create_new_site_api_sites_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SiteCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SiteResponse"];
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
    get_comprehensive_site_endpoint_api_sites_comprehensive__site_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
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
                    "application/json": components["schemas"]["SiteComprehensiveResponse"];
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
    get_site_api_sites__site_id__get: {
        parameters: {
            query?: {
                /** @description Return the site even if soft-deleted */
                include_deleted?: boolean;
            };
            header?: never;
            path: {
                site_id: number;
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
                    "application/json": components["schemas"]["SiteResponse"];
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
    update_site_endpoint_api_sites__site_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SiteUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SiteResponse"];
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
    delete_site_endpoint_api_sites__site_id__delete: {
        parameters: {
            query?: {
                /** @description soft: preserves site_id — restorable via /restore. hard: permanent deletion, requires confirm=true and no active devices. */
                mode?: "soft" | "hard";
                /** @description Must be true to execute a hard delete */
                confirm?: boolean;
            };
            header?: never;
            path: {
                site_id: number;
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
                    "application/json": components["schemas"]["SiteDeleteResponse"];
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
    restore_site_endpoint_api_sites__site_id__restore_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
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
                    "application/json": components["schemas"]["SiteResponse"];
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
}
