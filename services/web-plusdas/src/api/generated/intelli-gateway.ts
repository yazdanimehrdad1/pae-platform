// GENERATED from contracts/openapi/intelli-gateway.openapi.json by scripts/api-types.mjs.
// Do not edit: run `make api-types`. Import it as `@contracts/intelli-gateway`.

export interface paths {
    "/api/healthz": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Liveness
         * @description Dependency-free liveness check (the Docker HEALTHCHECK hits it).
         */
        get: operations["healthz_api_healthz_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/forecast/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** PV forecast health: active provider, fallbacks, last success per site */
        get: operations["forecast_health_api_v1_forecast_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/forecast/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Fetch new PV forecasts now (admin) */
        post: operations["refresh_forecast_api_v1_forecast_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Sites the user can access */
        get: operations["list_sites_api_v1_sites_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/ask": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Ask a question about a site */
        post: operations["ask_api_v1_sites__site_id__ask_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/forecast/series": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * The PV forecast over a window: AC power and weather (past: as forecast then)
         * @description Each 15-minute interval comes from the newest forecast issued at or before its start, so
         *     past intervals show what was predicted just before them (compare with actual output) and
         *     future ones the latest forecast. For charting next to measurements.
         */
        get: operations["get_forecast_series_api_v1_sites__site_id__forecast_series_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Tool specs Claude can call (mirrors MCP list_tools; for debugging) */
        get: operations["list_tools_api_v1_tools_get"];
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
        /** ArrayIntervalResponse */
        ArrayIntervalResponse: {
            /**
             * Array Id
             * @description backend-ot device id of the PV array
             */
            array_id: number;
            /** Pv Ac Kw */
            pv_ac_kw: number;
        };
        /** AskRequest */
        AskRequest: {
            /**
             * Conversation Id
             * @description Continue an earlier conversation; omit to start a new one.
             */
            conversation_id?: string | null;
            /** Question */
            question: string;
        };
        /** AskResponse */
        AskResponse: {
            /** Answer */
            answer: string;
            /** Conversation Id */
            conversation_id: string;
            /** Iterations */
            iterations: number;
            /** Model */
            model: string | null;
            /**
             * Stop Reason
             * @description end_turn (normal), max_tokens, refusal, max_iterations or timeout.
             */
            stop_reason: string;
            /** Tool Calls */
            tool_calls: components["schemas"]["ToolCallResponse"][];
            usage: components["schemas"]["UsageResponse"];
        };
        /** ErrorResponse */
        ErrorResponse: {
            /** Detail */
            detail: string;
        };
        /** ForecastHealthResponse */
        ForecastHealthResponse: {
            /** Active Provider */
            active_provider: string;
            /** Enabled */
            enabled: boolean;
            /** Fallback Providers */
            fallback_providers: string[];
            /** Sites */
            sites: components["schemas"]["SiteForecastHealthResponse"][];
        };
        /** ForecastIntervalResponse */
        ForecastIntervalResponse: {
            /**
             * Arrays
             * @description AC power per PV device; empty when the source predicts the site total only
             */
            arrays: components["schemas"]["ArrayIntervalResponse"][];
            /** Cloud Cover Pct */
            cloud_cover_pct: number | null;
            /**
             * Ghi
             * @description Global horizontal irradiance
             */
            ghi: number | null;
            /**
             * Interval End
             * Format: date-time
             */
            interval_end: string;
            /**
             * Interval Start
             * Format: date-time
             */
            interval_start: string;
            /**
             * Pv Ac Kw
             * @description Site AC power: the sum of its arrays
             */
            pv_ac_kw: number;
            /** Temp Air C */
            temp_air_c: number | null;
            /** Wind Speed Ms */
            wind_speed_ms: number | null;
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
        };
        JsonValue: unknown;
        /** PvForecastResponse */
        PvForecastResponse: {
            /**
             * Fallback Used
             * @description A fallback produced it: the primary source failed
             */
            fallback_used: boolean;
            /**
             * Interval Convention
             * @default mean over [interval_start, interval_end); times UTC
             */
            interval_convention: string;
            /** Intervals */
            intervals: components["schemas"]["ForecastIntervalResponse"][];
            /**
             * Issued At
             * Format: date-time
             */
            issued_at: string;
            /**
             * Provider
             * @description The source that produced this forecast
             */
            provider: string;
            /** Resolution Minutes */
            resolution_minutes: number;
            /** Site Id */
            site_id: number;
            /**
             * Source Kind
             * @description weather_model (weather + PV model) or pv_power
             */
            source_kind: string;
            /** Units */
            units?: {
                [key: string]: string;
            };
        };
        /** RefreshResponse */
        RefreshResponse: {
            /**
             * Finished At
             * Format: date-time
             */
            finished_at: string;
            /** Sites */
            sites: components["schemas"]["SiteRefreshResponse"][];
            /**
             * Started At
             * Format: date-time
             */
            started_at: string;
        };
        /** SiteForecastHealthResponse */
        SiteForecastHealthResponse: {
            /** Fallback In Use */
            fallback_in_use: boolean;
            /** Last Attempt At */
            last_attempt_at: string | null;
            /** Last Error */
            last_error: string | null;
            /** Last Provider */
            last_provider: string | null;
            /** Last Success At */
            last_success_at: string | null;
            /** Site Id */
            site_id: number;
            /** Stale */
            stale: boolean;
        };
        /** SiteRefreshResponse */
        SiteRefreshResponse: {
            /** Error */
            error: string | null;
            /** Fallback Used */
            fallback_used: boolean;
            /** Intervals */
            intervals: number;
            /** Ok */
            ok: boolean;
            /** Provider */
            provider: string | null;
            /** Site Id */
            site_id: number;
        };
        /** SiteResponse */
        SiteResponse: {
            /** Capacity Kw */
            capacity_kw: number | null;
            /** Description */
            description: string | null;
            /** Name */
            name: string;
            /** Site Id */
            site_id: number;
            /** Timezone */
            timezone: string;
        };
        /** ToolCallResponse */
        ToolCallResponse: {
            /** Args */
            args: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Duration Ms */
            duration_ms: number;
            /** Is Error */
            is_error: boolean;
            /** Name */
            name: string;
            /**
             * Summary
             * @description The start of the tool result, for display and debugging.
             */
            summary: string;
        };
        /** ToolSpecResponse */
        ToolSpecResponse: {
            /** Description */
            description: string;
            /** Input Schema */
            input_schema: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Name */
            name: string;
        };
        /** UsageResponse */
        UsageResponse: {
            /** Cache Creation Input Tokens */
            cache_creation_input_tokens: number;
            /** Cache Read Input Tokens */
            cache_read_input_tokens: number;
            /** Input Tokens */
            input_tokens: number;
            /** Output Tokens */
            output_tokens: number;
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
    healthz_api_healthz_get: {
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
    forecast_health_api_v1_forecast_health_get: {
        parameters: {
            query?: never;
            header?: {
                /** @description Dev auth: user id. */
                "x-user-id"?: string | null;
                /** @description Dev auth: comma-separated roles. */
                "x-roles"?: string | null;
                /** @description Dev auth: comma-separated site ids the user may access. */
                "x-site-ids"?: string | null;
            };
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
                    "application/json": components["schemas"]["ForecastHealthResponse"];
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
    refresh_forecast_api_v1_forecast_refresh_post: {
        parameters: {
            query?: {
                /** @description One site; omit for every forecastable site */
                site_id?: number | null;
            };
            header?: {
                /** @description Dev auth: user id. */
                "x-user-id"?: string | null;
                /** @description Dev auth: comma-separated roles. */
                "x-roles"?: string | null;
                /** @description Dev auth: comma-separated site ids the user may access. */
                "x-site-ids"?: string | null;
            };
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
                    "application/json": components["schemas"]["RefreshResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
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
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_sites_api_v1_sites_get: {
        parameters: {
            query?: never;
            header?: {
                /** @description Dev auth: user id. */
                "x-user-id"?: string | null;
                /** @description Dev auth: comma-separated roles. */
                "x-roles"?: string | null;
                /** @description Dev auth: comma-separated site ids the user may access. */
                "x-site-ids"?: string | null;
            };
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
    ask_api_v1_sites__site_id__ask_post: {
        parameters: {
            query?: never;
            header?: {
                /** @description Dev auth: user id. */
                "x-user-id"?: string | null;
                /** @description Dev auth: comma-separated roles. */
                "x-roles"?: string | null;
                /** @description Dev auth: comma-separated site ids the user may access. */
                "x-site-ids"?: string | null;
            };
            path: {
                site_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AskRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AskResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
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
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_forecast_series_api_v1_sites__site_id__forecast_series_get: {
        parameters: {
            query: {
                /** @description ISO 8601 with offset */
                start: string;
                /** @description ISO 8601 with offset; may be in the future */
                end: string;
            };
            header?: {
                /** @description Dev auth: user id. */
                "x-user-id"?: string | null;
                /** @description Dev auth: comma-separated roles. */
                "x-roles"?: string | null;
                /** @description Dev auth: comma-separated site ids the user may access. */
                "x-site-ids"?: string | null;
            };
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
                    "application/json": components["schemas"]["PvForecastResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description No forecast stored for the window */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Entity */
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
    list_tools_api_v1_tools_get: {
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
                    "application/json": components["schemas"]["ToolSpecResponse"][];
                };
            };
        };
    };
}
