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
    "/api/readyz": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Readiness
         * @description Ready to serve: its own Postgres answers (when one is configured). The deploy waits on it.
         */
        get: operations["readyz_api_readyz_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Log in: sets the session cookie */
        post: operations["login_api_v1_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Log out: ends the session and clears the cookie */
        post: operations["logout_api_v1_auth_logout_post"];
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
    "/api/v1/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The logged-in user */
        get: operations["me_api_v1_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/notes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Your notes, most recently updated first */
        get: operations["list_notes_api_v1_me_notes_get"];
        put?: never;
        /** Add a note */
        post: operations["create_note_api_v1_me_notes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/notes/{note_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Edit a note */
        put: operations["update_note_api_v1_me_notes__note_id__put"];
        post?: never;
        /** Delete a note */
        delete: operations["delete_note_api_v1_me_notes__note_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Change your own password (your other sessions end; this one stays) */
        put: operations["change_password_api_v1_me_password_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/preferences": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** All your preferences */
        get: operations["list_preferences_api_v1_me_preferences_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/preferences/{key}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** One preference */
        get: operations["get_preference_api_v1_me_preferences__key__get"];
        /** Set a preference (any JSON value) */
        put: operations["put_preference_api_v1_me_preferences__key__put"];
        post?: never;
        /** Remove a preference */
        delete: operations["delete_preference_api_v1_me_preferences__key__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/trends": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Your saved trends, in your order */
        get: operations["list_trends_api_v1_me_trends_get"];
        put?: never;
        /** Save a trend (added last) */
        post: operations["create_trend_api_v1_me_trends_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/trends/order": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Reorder your trends */
        put: operations["reorder_trends_api_v1_me_trends_order_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/me/trends/{trend_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Replace a trend's name, points, scale and styles */
        put: operations["update_trend_api_v1_me_trends__trend_id__put"];
        post?: never;
        /** Delete a trend */
        delete: operations["delete_trend_api_v1_me_trends__trend_id__delete"];
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
    "/api/v1/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Every account, by email */
        get: operations["list_users_api_v1_users_get"];
        put?: never;
        /** Add an account */
        post: operations["create_user_api_v1_users_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Change an account's name, role, or disabled state */
        patch: operations["update_user_api_v1_users__user_id__patch"];
        trace?: never;
    };
    "/api/v1/users/{user_id}/password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Set an account's password (ends its sessions) */
        put: operations["reset_password_api_v1_users__user_id__password_put"];
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
        /** LoginRequest */
        LoginRequest: {
            /**
             * Email
             * @description Case-insensitive.
             */
            email: string;
            /** Password */
            password: string;
        };
        /**
         * MeResponse
         * @description The logged-in user.
         */
        MeResponse: {
            /** Display Name */
            display_name: string;
            /** Email */
            email: string;
            /** Id */
            id: number;
            /**
             * Role
             * @enum {string}
             */
            role: "engineer" | "admin" | "monitor";
        };
        /** Note */
        Note: {
            /** Content */
            content: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Id */
            id: number;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** NoteCreateRequest */
        NoteCreateRequest: {
            /** Content */
            content: string;
            /**
             * Created At
             * @description Only to keep the dates of a note imported from the browser.
             */
            created_at?: string | null;
            /**
             * Updated At
             * @description As created_at.
             */
            updated_at?: string | null;
        };
        /** NoteUpdateRequest */
        NoteUpdateRequest: {
            /** Content */
            content: string;
        };
        /** PasswordChangeRequest */
        PasswordChangeRequest: {
            /** Current Password */
            current_password: string;
            /** New Password */
            new_password: string;
        };
        /** PasswordResetRequest */
        PasswordResetRequest: {
            /** Password */
            password: string;
        };
        /** Preference */
        Preference: {
            /** Key */
            key: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            value: components["schemas"]["JsonValue"];
        };
        /** PreferenceRequest */
        PreferenceRequest: {
            /** @description Any JSON value, at most 64 KiB serialized. */
            value: components["schemas"]["JsonValue"];
        };
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
        /** ReadinessResponse */
        ReadinessResponse: {
            /**
             * Database
             * @description Its own Postgres: not_configured when DATABASE_URL is unset (forecasts in memory).
             * @enum {string}
             */
            database: "ok" | "unavailable" | "not_configured";
            /** Ok */
            ok: boolean;
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
        /** SavedTrend */
        SavedTrend: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Id */
            id: number;
            /** Name */
            name: string;
            /**
             * Points
             * @description Historian selection ids, as web-plusdas builds them.
             */
            points?: string[];
            /**
             * Position
             * @description The user's order, 0 first.
             */
            position: number;
            /**
             * Scale
             * @description null: the default (per unit).
             */
            scale?: ("per-unit" | "per-point" | "shared") | null;
            /**
             * Styles
             * @description By selection id; null or a missing entry: the defaults.
             */
            styles?: {
                [key: string]: components["schemas"]["SeriesStyle"];
            } | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * SeriesStyle
         * @description What the user changed in how one selection is drawn; a missing field uses the default.
         */
        SeriesStyle: {
            /** Color */
            color?: string | null;
            /** Dash */
            dash?: ("solid" | "dashed" | "dotted") | null;
            /** Width */
            width?: number | null;
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
        /** TrendDefinition */
        TrendDefinition: {
            /** Name */
            name: string;
            /**
             * Points
             * @description Historian selection ids, as web-plusdas builds them.
             */
            points?: string[];
            /**
             * Scale
             * @description null: the default (per unit).
             */
            scale?: ("per-unit" | "per-point" | "shared") | null;
            /**
             * Styles
             * @description By selection id; null or a missing entry: the defaults.
             */
            styles?: {
                [key: string]: components["schemas"]["SeriesStyle"];
            } | null;
        };
        /** TrendOrderRequest */
        TrendOrderRequest: {
            /**
             * Trend Ids
             * @description Every one of your trend ids, in the new order.
             */
            trend_ids: number[];
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
        /** UserCreateRequest */
        UserCreateRequest: {
            /** Display Name */
            display_name: string;
            /**
             * Email
             * @description The sign-in name; stored lower-case (name@domain.tld)
             */
            email: string;
            /** Password */
            password: string;
            /**
             * Role
             * @enum {string}
             */
            role: "engineer" | "admin" | "monitor";
        };
        /**
         * UserResponse
         * @description An account, as an admin sees it (never its password).
         */
        UserResponse: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Disabled */
            disabled: boolean;
            /** Display Name */
            display_name: string;
            /** Email */
            email: string;
            /** Id */
            id: number;
            /** Last Login At */
            last_login_at: string | null;
            /**
             * Role
             * @enum {string}
             */
            role: "engineer" | "admin" | "monitor";
        };
        /**
         * UserUpdateRequest
         * @description Only the fields given change.
         */
        UserUpdateRequest: {
            /**
             * Disabled
             * @description true also ends the user's sessions.
             */
            disabled?: boolean | null;
            /** Display Name */
            display_name?: string | null;
            /** Role */
            role?: ("engineer" | "admin" | "monitor") | null;
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
    readyz_api_readyz_get: {
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
                    "application/json": components["schemas"]["ReadinessResponse"];
                };
            };
            /** @description The database is unreachable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadinessResponse"];
                };
            };
        };
    };
    login_api_v1_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeResponse"];
                };
            };
            /** @description Wrong email or password */
            401: {
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
    logout_api_v1_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
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
        };
    };
    forecast_health_api_v1_forecast_health_get: {
        parameters: {
            query?: never;
            header?: {
                /** @description Dev auth only: user id. */
                "x-user-id"?: string | null;
                /** @description Dev auth only: comma-separated roles. */
                "x-roles"?: string | null;
                /** @description Dev auth only: comma-separated site ids the user may access. */
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
                /** @description Dev auth only: user id. */
                "x-user-id"?: string | null;
                /** @description Dev auth only: comma-separated roles. */
                "x-roles"?: string | null;
                /** @description Dev auth only: comma-separated site ids the user may access. */
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
    me_api_v1_me_get: {
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
                    "application/json": components["schemas"]["MeResponse"];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_notes_api_v1_me_notes_get: {
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
                    "application/json": components["schemas"]["Note"][];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    create_note_api_v1_me_notes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NoteCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Note"];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid, or over a per-user limit */
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
    update_note_api_v1_me_notes__note_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                note_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NoteUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Note"];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not one of yours */
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
    delete_note_api_v1_me_notes__note_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                note_id: number;
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
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not one of yours */
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
    change_password_api_v1_me_password_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PasswordChangeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The current password is wrong */
            403: {
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
    list_preferences_api_v1_me_preferences_get: {
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
                    "application/json": components["schemas"]["Preference"][];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_preference_api_v1_me_preferences__key__get: {
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
                    "application/json": components["schemas"]["Preference"];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not one of yours */
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
    put_preference_api_v1_me_preferences__key__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                key: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PreferenceRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Preference"];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid, or over a per-user limit */
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
    delete_preference_api_v1_me_preferences__key__delete: {
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
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not one of yours */
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
    list_trends_api_v1_me_trends_get: {
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
                    "application/json": components["schemas"]["SavedTrend"][];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    create_trend_api_v1_me_trends_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TrendDefinition"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SavedTrend"];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid, or over a per-user limit */
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
    reorder_trends_api_v1_me_trends_order_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TrendOrderRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SavedTrend"][];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Invalid, or over a per-user limit */
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
    update_trend_api_v1_me_trends__trend_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                trend_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TrendDefinition"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SavedTrend"];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not one of yours */
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
    delete_trend_api_v1_me_trends__trend_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                trend_id: number;
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
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not one of yours */
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
    list_sites_api_v1_sites_get: {
        parameters: {
            query?: never;
            header?: {
                /** @description Dev auth only: user id. */
                "x-user-id"?: string | null;
                /** @description Dev auth only: comma-separated roles. */
                "x-roles"?: string | null;
                /** @description Dev auth only: comma-separated site ids the user may access. */
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
                /** @description Dev auth only: user id. */
                "x-user-id"?: string | null;
                /** @description Dev auth only: comma-separated roles. */
                "x-roles"?: string | null;
                /** @description Dev auth only: comma-separated site ids the user may access. */
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
                /** @description Dev auth only: user id. */
                "x-user-id"?: string | null;
                /** @description Dev auth only: comma-separated roles. */
                "x-roles"?: string | null;
                /** @description Dev auth only: comma-separated site ids the user may access. */
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
            header?: {
                /** @description Dev auth only: user id. */
                "x-user-id"?: string | null;
                /** @description Dev auth only: comma-separated roles. */
                "x-roles"?: string | null;
                /** @description Dev auth only: comma-separated site ids the user may access. */
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
                    "application/json": components["schemas"]["ToolSpecResponse"][];
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
    list_users_api_v1_users_get: {
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
                    "application/json": components["schemas"]["UserResponse"][];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an admin */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    create_user_api_v1_users_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserResponse"];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an admin */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The email is taken */
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
    update_user_api_v1_users__user_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserResponse"];
                };
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an admin */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description No such user */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description e.g. demoting or disabling yourself */
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
    reset_password_api_v1_users__user_id__password_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PasswordResetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Not logged in */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an admin */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description No such user */
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
}
