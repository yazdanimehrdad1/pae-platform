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
    "/api/v1/site-profiles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Every synced or onboarded site: approved version and pending change count */
        get: operations["list_site_profiles_api_v1_site_profiles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/site-profiles/sync": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Read every site from backend-ot now (approves nothing) */
        post: operations["sync_all_site_profiles_api_v1_site_profiles_sync_post"];
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
    "/api/v1/sites/{site_id}/functions/{name}/test-run": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Run an approved site function exactly as the AI would, and see what it gets */
        post: operations["test_run_site_function_api_v1_sites__site_id__functions__name__test_run_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The draft (or published) knowledge */
        get: operations["get_knowledge_api_v1_sites__site_id__knowledge_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge/coverage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Which status/alarm points still need a guide, devices without facts, orphans */
        get: operations["get_coverage_api_v1_sites__site_id__knowledge_coverage_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge/device-facts/{device_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Write a device's ratings and notes into the draft */
        put: operations["put_device_facts_api_v1_sites__site_id__knowledge_device_facts__device_id__put"];
        post?: never;
        /** Remove a device's ratings and notes in the draft */
        delete: operations["delete_device_facts_api_v1_sites__site_id__knowledge_device_facts__device_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge/documents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Add a document (manual, IM script, procedure, experience note) to the draft */
        post: operations["create_document_api_v1_sites__site_id__knowledge_documents_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge/documents/{document_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Change a document in the draft */
        put: operations["update_document_api_v1_sites__site_id__knowledge_documents__document_id__put"];
        post?: never;
        /** Remove a document in the draft */
        delete: operations["delete_document_api_v1_sites__site_id__knowledge_documents__document_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge/draft": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Discard the whole draft */
        delete: operations["discard_draft_api_v1_sites__site_id__knowledge_draft_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge/draft/revert": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Put some draft changes back as published */
        post: operations["revert_draft_items_api_v1_sites__site_id__knowledge_draft_revert_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge/point-guides/{device_id}/{point_name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Write a point's guide into the draft (point name within its device) */
        put: operations["put_point_guide_api_v1_sites__site_id__knowledge_point_guides__device_id___point_name__put"];
        post?: never;
        /** Remove a point's guide in the draft */
        delete: operations["delete_point_guide_api_v1_sites__site_id__knowledge_point_guides__device_id___point_name__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Publish the whole draft: the AI uses it from now on */
        post: operations["publish_api_v1_sites__site_id__knowledge_publish_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge/site-prompts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Add a site prompt (general information about the site) after the others, to the draft */
        post: operations["create_site_prompt_api_v1_sites__site_id__knowledge_site_prompts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge/site-prompts/{prompt_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Change a site prompt's name, text and links in the draft */
        put: operations["update_site_prompt_api_v1_sites__site_id__knowledge_site_prompts__prompt_id__put"];
        post?: never;
        /** Remove a site prompt in the draft */
        delete: operations["delete_site_prompt_api_v1_sites__site_id__knowledge_site_prompts__prompt_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Every published version, newest first */
        get: operations["list_versions_api_v1_sites__site_id__knowledge_versions_get"];
        put?: never;
        post?: never;
        /** Delete older published versions (never the one the AI uses); the versions left */
        delete: operations["delete_versions_api_v1_sites__site_id__knowledge_versions_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge/versions/{version}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** One published version */
        get: operations["get_version_api_v1_sites__site_id__knowledge_versions__version__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/knowledge/versions/{version}/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Publish an earlier version's content again, as a new version */
        post: operations["restore_version_api_v1_sites__site_id__knowledge_versions__version__restore_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The site's approved profile: what the AI knows of its facts */
        get: operations["get_site_profile_api_v1_sites__site_id__profile_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/profile/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Approve pending changes into a new profile version (onboards a new site) */
        post: operations["approve_site_profile_changes_api_v1_sites__site_id__profile_approve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/profile/changes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Differences between backend-ot (as last read) and the approved profile */
        get: operations["get_pending_changes_api_v1_sites__site_id__profile_changes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/profile/sync": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Read the site from backend-ot now and list the pending changes */
        post: operations["sync_site_profile_api_v1_sites__site_id__profile_sync_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{site_id}/profile/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Every approved version, newest first */
        get: operations["list_site_profile_versions_api_v1_sites__site_id__profile_versions_get"];
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
        /** ApproveChangesRequest */
        ApproveChangesRequest: {
            /**
             * Change Ids
             * @description The pending changes to approve (their change_id). Omit to approve them all.
             */
            change_ids?: string[] | null;
            /**
             * Fetched At
             * @description The fetched_at of the pending changes you reviewed. When backend-ot was read again since, nothing is approved (409): review the changes again.
             */
            fetched_at?: string | null;
        };
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
        /**
         * ChangeKind
         * @enum {string}
         */
        ChangeKind: "added" | "removed" | "changed";
        /**
         * ChangeTarget
         * @enum {string}
         */
        ChangeTarget: "site" | "device" | "point" | "topology" | "function";
        /** Device */
        Device: {
            /** Description */
            description?: string | null;
            /** Device Id */
            device_id: number;
            /** Model */
            model?: string | null;
            /** Name */
            name: string;
            /** Type */
            type: string;
            /** Vendor */
            vendor?: string | null;
        };
        /** DeviceFacts */
        DeviceFacts: {
            /** Author */
            author?: string | null;
            /** Device Id */
            device_id: number;
            /** Notes */
            notes?: string | null;
            /**
             * Ratings
             * @default []
             */
            ratings: components["schemas"]["DeviceRating"][];
            /** Site Id */
            site_id: number;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** DeviceFactsRequest */
        DeviceFactsRequest: {
            /**
             * Draft Revision
             * @description The draft revision you loaded (0 = there was no draft). When someone saved since, nothing changes (409): reload. Omit to skip the check.
             */
            draft_revision?: number | null;
            /** Notes */
            notes?: string | null;
            /** Ratings */
            ratings?: components["schemas"]["DeviceRating"][];
        };
        /**
         * DeviceRating
         * @description One rating of a device, e.g. BESS energy capacity 80 MWh.
         */
        DeviceRating: {
            /** Name */
            name: string;
            /** Unit */
            unit: string;
            /** Value */
            value: number;
        };
        /** DocumentCreatedResponse */
        DocumentCreatedResponse: {
            /**
             * Changes
             * @description What publishing the draft would change.
             */
            changes: components["schemas"]["KnowledgeChange"][];
            /** @description The draft, or the published knowledge. */
            content: components["schemas"]["SiteKnowledge"];
            /** Document Id */
            document_id: string;
            /**
             * Draft Revision
             * @description 0 = no draft: the content is the published one.
             */
            draft_revision: number;
            /** Draft Updated At */
            draft_updated_at: string | null;
            /** Draft Updated By */
            draft_updated_by: string | null;
            /** Published At */
            published_at: string | null;
            /** Published By */
            published_by: string | null;
            /** Published Version */
            published_version: number | null;
            /** Site Id */
            site_id: number;
        };
        /** DocumentRequest */
        DocumentRequest: {
            /**
             * Body
             * @description Pasted text (Markdown).
             */
            body: string;
            /** Device Id */
            device_id?: number | null;
            /**
             * Draft Revision
             * @description The draft revision you loaded (0 = there was no draft). When someone saved since, nothing changes (409): reload. Omit to skip the check.
             */
            draft_revision?: number | null;
            kind: components["schemas"]["KnowledgeKind"];
            /** Point Names */
            point_names?: string[];
            /** Title */
            title: string;
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
        /**
         * GuideSeverity
         * @enum {string}
         */
        GuideSeverity: "fault" | "warning" | "info";
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
        /**
         * KnowledgeChange
         * @description One draft item that differs from the published knowledge. item_key:
         *     `point:<device_id>:<point name>`, `document:<document_id>`, `device:<device_id>` or
         *     `prompt:<prompt_id>`.
         */
        KnowledgeChange: {
            /** Item Key */
            item_key: string;
            item_kind: components["schemas"]["KnowledgeItemKind"];
            /**
             * Kind
             * @enum {string}
             */
            kind: "added" | "removed" | "changed";
            /** Summary */
            summary: string;
        };
        /**
         * KnowledgeCoverage
         * @description What the site's knowledge covers: the onboarding to-do list (on the draft when there is
         *     one, otherwise on the published knowledge).
         */
        KnowledgeCoverage: {
            /** Devices */
            devices: number;
            /** Devices With Facts */
            devices_with_facts: number;
            /** Discrete Points */
            discrete_points: number;
            /** Discrete With Guide */
            discrete_with_guide: number;
            /** Documents By Kind */
            documents_by_kind: {
                [key: string]: number;
            };
            /** Guides */
            guides: number;
            /** Missing Guides */
            missing_guides: components["schemas"]["MissingGuide"][];
            /** Orphaned */
            orphaned: string[];
            /** Points */
            points: number;
            /** Site Id */
            site_id: number;
        };
        /** KnowledgeDocument */
        KnowledgeDocument: {
            /** Author */
            author?: string | null;
            /** Body */
            body: string;
            /** Device Id */
            device_id?: number | null;
            /** Document Id */
            document_id?: string;
            kind: components["schemas"]["KnowledgeKind"];
            /**
             * Point Names
             * @default []
             */
            point_names: string[];
            /** Site Id */
            site_id: number;
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * KnowledgeItemKind
         * @enum {string}
         */
        KnowledgeItemKind: "point_guide" | "document" | "device_facts" | "site_prompt";
        /**
         * KnowledgeKind
         * @enum {string}
         */
        KnowledgeKind: "manual" | "im_script" | "procedure" | "experience_note";
        /**
         * KnowledgeStateResponse
         * @description The site's knowledge for an admin: what is published, and the draft (the next publish).
         */
        KnowledgeStateResponse: {
            /**
             * Changes
             * @description What publishing the draft would change.
             */
            changes: components["schemas"]["KnowledgeChange"][];
            /** @description The draft, or the published knowledge. */
            content: components["schemas"]["SiteKnowledge"];
            /**
             * Draft Revision
             * @description 0 = no draft: the content is the published one.
             */
            draft_revision: number;
            /** Draft Updated At */
            draft_updated_at: string | null;
            /** Draft Updated By */
            draft_updated_by: string | null;
            /** Published At */
            published_at: string | null;
            /** Published By */
            published_by: string | null;
            /** Published Version */
            published_version: number | null;
            /** Site Id */
            site_id: number;
        };
        /**
         * KnowledgeVersion
         * @description One publish: what the AI uses, from published_at until the next version.
         */
        KnowledgeVersion: {
            /**
             * Change Ids
             * @default []
             */
            change_ids: string[];
            content: components["schemas"]["SiteKnowledge"];
            /**
             * Published At
             * Format: date-time
             */
            published_at: string;
            /** Published By */
            published_by: string;
            /** Restored From */
            restored_from?: number | null;
            /** Site Id */
            site_id: number;
            /** Version */
            version: number;
        };
        /** KnowledgeVersionSummary */
        KnowledgeVersionSummary: {
            /** Change Ids */
            change_ids: string[];
            /** Device Facts */
            device_facts: number;
            /** Documents */
            documents: number;
            /** Point Guides */
            point_guides: number;
            /**
             * Published At
             * Format: date-time
             */
            published_at: string;
            /** Published By */
            published_by: string;
            /** Restored From */
            restored_from: number | null;
            /** Site Prompts */
            site_prompts: number;
            /** Version */
            version: number;
        };
        /**
         * LimitCondition
         * @enum {string}
         */
        LimitCondition: "above" | "below";
        /**
         * LimitGuide
         * @description A limit on an analog point, e.g. cabinet temperature above 60 degC = derating.
         */
        LimitGuide: {
            /**
             * Checks
             * @default []
             */
            checks: string[];
            condition: components["schemas"]["LimitCondition"];
            /** Message */
            message: string;
            /**
             * Probable Causes
             * @default []
             */
            probable_causes: string[];
            severity: components["schemas"]["GuideSeverity"];
            /** Value */
            value: number;
        };
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
        /**
         * MissingGuide
         * @description An approved status, alarm or fault-code point with no guide (in the draft or published).
         */
        MissingGuide: {
            /** Device Id */
            device_id: number;
            /** Point Class */
            point_class?: string | null;
            /** Point Name */
            point_name: string;
            /** Qualified Name */
            qualified_name: string;
            /**
             * Reason
             * @enum {string}
             */
            reason: "alarm" | "states" | "bits";
        };
        /** NormalRange */
        NormalRange: {
            /** Max */
            max?: number | null;
            /** Min */
            min?: number | null;
            /** Note */
            note?: string | null;
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
        /** PendingChanges */
        PendingChanges: {
            /** Approved Version */
            approved_version: number | null;
            /** Changes */
            changes: components["schemas"]["ProfileChange"][];
            /**
             * Fetched At
             * Format: date-time
             */
            fetched_at: string;
            /** Site Id */
            site_id: number;
        };
        /**
         * PointClass
         * @enum {string}
         */
        PointClass: "ANALOG" | "BINARY" | "ALARM" | "CONTROL";
        /**
         * PointGuide
         * @description Engineer-written guide for one point of one site device.
         */
        PointGuide: {
            /** Author */
            author?: string | null;
            /** Device Id */
            device_id: number;
            /**
             * Limits
             * @default []
             */
            limits: components["schemas"]["LimitGuide"][];
            /** Meaning */
            meaning: string;
            normal_range?: components["schemas"]["NormalRange"] | null;
            /** Point Name */
            point_name: string;
            /**
             * Related Points
             * @default []
             */
            related_points: string[];
            /** Site Id */
            site_id: number;
            /**
             * States
             * @default []
             */
            states: components["schemas"]["StateGuide"][];
            /** Unit Note */
            unit_note?: string | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** PointGuideRequest */
        PointGuideRequest: {
            /**
             * Draft Revision
             * @description The draft revision you loaded (0 = there was no draft). When someone saved since, nothing changes (409): reload. Omit to skip the check.
             */
            draft_revision?: number | null;
            /** Limits */
            limits?: components["schemas"]["LimitGuide"][];
            /** Meaning */
            meaning: string;
            normal_range?: components["schemas"]["NormalRange"] | null;
            /** Related Points */
            related_points?: string[];
            /** States */
            states?: components["schemas"]["StateGuide"][];
            /** Unit Note */
            unit_note?: string | null;
        };
        /**
         * PointInfo
         * @description One data point (tag) in a site's catalog. `name` is unique within a site.
         */
        PointInfo: {
            /** Bit Labels */
            bit_labels?: {
                [key: string]: string;
            };
            /**
             * Data Type
             * @default float32
             */
            data_type: string;
            /** Description */
            description?: string | null;
            /** Device Id */
            device_id: number;
            /** Device Name */
            device_name: string;
            /** Enum Labels */
            enum_labels?: {
                [key: string]: string;
            };
            /** Equipment */
            equipment: string;
            /** Name */
            name: string;
            point_class?: components["schemas"]["PointClass"] | null;
            /** Severity */
            severity?: string | null;
            /** Unit */
            unit?: string | null;
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
        /**
         * ProfileChange
         * @description One difference between the approved profile and backend-ot's current catalog.
         *
         *     change_id is stable for the same difference: `site`, `topology`, `device:<device_id>`,
         *     `point:<device_id>:<point name in its device>`, `function:<name>`. A device added or removed
         *     carries its points (they are not listed separately).
         */
        ProfileChange: {
            /** Change Id */
            change_id: string;
            /** Device Id */
            device_id?: number | null;
            /**
             * Fields
             * @default []
             */
            fields: string[];
            /** Function Name */
            function_name?: string | null;
            kind: components["schemas"]["ChangeKind"];
            /** Point Name */
            point_name?: string | null;
            /** Summary */
            summary: string;
            target: components["schemas"]["ChangeTarget"];
        };
        /**
         * ProfileVersion
         * @description One approved version of a site's profile. The highest version is the one the AI uses.
         */
        ProfileVersion: {
            /**
             * Approved At
             * Format: date-time
             */
            approved_at: string;
            /** Approved By */
            approved_by: string;
            catalog: components["schemas"]["SiteCatalog"];
            /**
             * Change Ids
             * @default []
             */
            change_ids: string[];
            /** Site Id */
            site_id: number;
            /** Version */
            version: number;
        };
        /** ProfileVersionSummary */
        ProfileVersionSummary: {
            /**
             * Approved At
             * Format: date-time
             */
            approved_at: string;
            /** Approved By */
            approved_by: string;
            /** Change Ids */
            change_ids: string[];
            /** Devices */
            devices: number;
            /**
             * Functions
             * @default 0
             */
            functions: number;
            /** Points */
            points: number;
            /** Site Id */
            site_id: number;
            /** Version */
            version: number;
        };
        /**
         * PromptPointLink
         * @description A point a site prompt is about: the site device and the point's name on it.
         */
        PromptPointLink: {
            /** Device Id */
            device_id: number;
            /** Point Name */
            point_name: string;
        };
        /** PublishRequest */
        PublishRequest: {
            /**
             * Draft Revision
             * @description The draft revision you loaded (0 = there was no draft). When someone saved since, nothing changes (409): reload. Omit to skip the check.
             */
            draft_revision?: number | null;
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
        /** RevertRequest */
        RevertRequest: {
            /**
             * Draft Revision
             * @description The draft revision you loaded (0 = there was no draft). When someone saved since, nothing changes (409): reload. Omit to skip the check.
             */
            draft_revision?: number | null;
            /**
             * Item Keys
             * @description The draft changes to put back.
             */
            item_keys: string[];
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
        /** Site */
        Site: {
            /** Capacity Kw */
            capacity_kw?: number | null;
            /** Description */
            description?: string | null;
            /** Latitude */
            latitude?: number | null;
            /** Longitude */
            longitude?: number | null;
            /** Name */
            name: string;
            /** Site Id */
            site_id: number;
            /**
             * Timezone
             * @default UTC
             */
            timezone: string;
        };
        /**
         * SiteCatalog
         * @description A site's facts at one moment: what was fetched from backend-ot, or what was approved.
         */
        SiteCatalog: {
            /**
             * Devices
             * @default []
             */
            devices: components["schemas"]["Device"][];
            /**
             * Functions
             * @default []
             */
            functions: components["schemas"]["SiteFunction"][];
            /**
             * Points
             * @default []
             */
            points: components["schemas"]["PointInfo"][];
            site: components["schemas"]["Site"];
            /**
             * @default {
             *       "connections": [],
             *       "nodes": []
             *     }
             */
            topology: components["schemas"]["Topology"];
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
        /**
         * SiteFunction
         * @description A calculation backend-ot runs for a site (e.g. a BESS's round-trip efficiency). kind
         *     `device` runs for one device; device_types limits which (empty: any device).
         */
        SiteFunction: {
            /**
             * Device Types
             * @default []
             */
            device_types: string[];
            /**
             * Kind
             * @enum {string}
             */
            kind: "common" | "site" | "device";
            /** Name */
            name: string;
            /**
             * Output
             * @default scalar
             * @enum {string}
             */
            output: "scalar" | "series";
            /**
             * Parameters
             * @default []
             */
            parameters: components["schemas"]["SiteFunctionParameter"][];
            /** Summary */
            summary: string;
        };
        /**
         * SiteFunctionParameter
         * @description A query parameter a function takes besides the time window.
         */
        SiteFunctionParameter: {
            /** Default */
            default?: number | string | boolean | null;
            /** Description */
            description?: string | null;
            /** Maximum */
            maximum?: number | null;
            /** Minimum */
            minimum?: number | null;
            /** Name */
            name: string;
            /**
             * Required
             * @default false
             */
            required: boolean;
            /** Type */
            type: string;
        };
        /** SiteFunctionTestRunRequest */
        SiteFunctionTestRunRequest: {
            /**
             * Device Id
             * @description Device functions only: the approved device to run it for
             */
            device_id?: number | null;
            /**
             * End
             * Format: date-time
             * @description End of the window, ISO 8601 with a UTC offset
             */
            end: string;
            /**
             * Parameters
             * @description Extra parameters the function declares; omit for their defaults
             */
            parameters?: {
                [key: string]: number | string | boolean;
            };
            /**
             * Start
             * Format: date-time
             * @description Start of the window, ISO 8601 with a UTC offset
             */
            start: string;
        };
        /**
         * SiteFunctionTestRunResponse
         * @description What the AI's run_site_function tool would return for the same request.
         */
        SiteFunctionTestRunResponse: {
            /** Device Id */
            device_id?: number | null;
            /**
             * End
             * Format: date-time
             */
            end: string;
            /** Function */
            function: string;
            /** Result */
            result: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /**
             * Start
             * Format: date-time
             */
            start: string;
        };
        /**
         * SiteKnowledge
         * @description Everything engineers wrote for one site. Point guides name the point within its device
         *     (`point_name` without the `DEVICE.` prefix), so a device rename doesn't orphan them.
         */
        SiteKnowledge: {
            /**
             * Device Facts
             * @default []
             */
            device_facts: components["schemas"]["DeviceFacts"][];
            /**
             * Documents
             * @default []
             */
            documents: components["schemas"]["KnowledgeDocument"][];
            /**
             * Point Guides
             * @default []
             */
            point_guides: components["schemas"]["PointGuide"][];
            /**
             * Site Prompts
             * @default []
             */
            site_prompts: components["schemas"]["SitePrompt"][];
        };
        /**
         * SiteProfileStatus
         * @description One site as the admin sees it: onboarded or not, and how many changes wait.
         */
        SiteProfileStatus: {
            /** Approved At */
            approved_at?: string | null;
            /** Approved Version */
            approved_version?: number | null;
            /** Fetched At */
            fetched_at?: string | null;
            /** Name */
            name: string;
            /**
             * Pending Changes
             * @default 0
             */
            pending_changes: number;
            /** Site Id */
            site_id: number;
        };
        /**
         * SitePrompt
         * @description One part of the site's general information for the AI (overview, how the site runs, ...),
         *     written by an admin as several named texts instead of one long prompt. Kept in `position`
         *     order (the order they were added); the AI reads them all, first, in its site context.
         */
        SitePrompt: {
            /** Author */
            author?: string | null;
            /**
             * @default {
             *       "devices": [],
             *       "documents": [],
             *       "functions": [],
             *       "points": []
             *     }
             */
            links: components["schemas"]["SitePromptLinks"];
            /** Name */
            name: string;
            /** Position */
            position: number;
            /** Prompt Id */
            prompt_id?: string;
            /** Site Id */
            site_id: number;
            /** Text */
            text: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** SitePromptCreatedResponse */
        SitePromptCreatedResponse: {
            /**
             * Changes
             * @description What publishing the draft would change.
             */
            changes: components["schemas"]["KnowledgeChange"][];
            /** @description The draft, or the published knowledge. */
            content: components["schemas"]["SiteKnowledge"];
            /**
             * Draft Revision
             * @description 0 = no draft: the content is the published one.
             */
            draft_revision: number;
            /** Draft Updated At */
            draft_updated_at: string | null;
            /** Draft Updated By */
            draft_updated_by: string | null;
            /** Prompt Id */
            prompt_id: string;
            /** Published At */
            published_at: string | null;
            /** Published By */
            published_by: string | null;
            /** Published Version */
            published_version: number | null;
            /** Site Id */
            site_id: number;
        };
        /**
         * SitePromptLinks
         * @description What a site prompt is about, all optional: approved points (and so their guides), site
         *     functions (by name), documents (by id) and device ratings (by device). Kept sorted and
         *     without repeats so an unchanged prompt never shows as an edit.
         */
        SitePromptLinks: {
            /**
             * Devices
             * @default []
             */
            devices: number[];
            /**
             * Documents
             * @default []
             */
            documents: string[];
            /**
             * Functions
             * @default []
             */
            functions: string[];
            /**
             * Points
             * @default []
             */
            points: components["schemas"]["PromptPointLink"][];
        };
        /** SitePromptRequest */
        SitePromptRequest: {
            /**
             * Draft Revision
             * @description The draft revision you loaded (0 = there was no draft). When someone saved since, nothing changes (409): reload. Omit to skip the check.
             */
            draft_revision?: number | null;
            /** @description Optional: the approved points, site functions, documents and device ratings this prompt is about, so the AI connects them. */
            links?: components["schemas"]["SitePromptLinks"];
            /**
             * Name
             * @description e.g. 'Overview', 'Startup'.
             */
            name: string;
            /**
             * Text
             * @description The information for the AI (Markdown).
             */
            text: string;
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
        /**
         * StateGuide
         * @description What one enum value, bit or vendor fault code means, and what to do about it.
         */
        StateGuide: {
            /**
             * Checks
             * @default []
             */
            checks: string[];
            /** Code */
            code: number;
            kind: components["schemas"]["StateKind"];
            /** Label */
            label: string;
            /** Meaning */
            meaning?: string | null;
            /** Message */
            message: string;
            /**
             * Probable Causes
             * @default []
             */
            probable_causes: string[];
            /**
             * Related Points
             * @default []
             */
            related_points: string[];
            /** Safety Note */
            safety_note?: string | null;
            severity: components["schemas"]["GuideSeverity"];
        };
        /**
         * StateKind
         * @enum {string}
         */
        StateKind: "enum_value" | "bit" | "fault_code";
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
        /**
         * Topology
         * @description The single-line diagram, condensed: what is connected to what.
         */
        Topology: {
            /**
             * Connections
             * @default []
             */
            connections: components["schemas"]["TopologyConnection"][];
            /**
             * Nodes
             * @default []
             */
            nodes: components["schemas"]["TopologyNode"][];
        };
        /** TopologyConnection */
        TopologyConnection: {
            /** From Id */
            from_id: string;
            /** To Id */
            to_id: string;
        };
        /** TopologyNode */
        TopologyNode: {
            /** Device Id */
            device_id?: number | null;
            /** Name */
            name: string;
            /** Node Id */
            node_id: string;
            /** Type */
            type: string;
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
    list_site_profiles_api_v1_site_profiles_get: {
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
                    "application/json": components["schemas"]["SiteProfileStatus"][];
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
    sync_all_site_profiles_api_v1_site_profiles_sync_post: {
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
                    "application/json": components["schemas"]["SiteProfileStatus"][];
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
            /** @description backend-ot unreachable */
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
    test_run_site_function_api_v1_sites__site_id__functions__name__test_run_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SiteFunctionTestRunRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SiteFunctionTestRunResponse"];
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
            /** @description No such approved function or device */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Bad window or parameters, or backend-ot refused it */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description backend-ot unreachable */
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
    get_knowledge_api_v1_sites__site_id__knowledge_get: {
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
                    "application/json": components["schemas"]["KnowledgeStateResponse"];
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
            /** @description Not onboarded, or no such item */
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
    get_coverage_api_v1_sites__site_id__knowledge_coverage_get: {
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
                    "application/json": components["schemas"]["KnowledgeCoverage"];
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
            /** @description Not onboarded, or no such item */
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
    put_device_facts_api_v1_sites__site_id__knowledge_device_facts__device_id__put: {
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
                "application/json": components["schemas"]["DeviceFactsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeStateResponse"];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The draft changed since draft_revision */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an approved point/device, or a secret */
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
    delete_device_facts_api_v1_sites__site_id__knowledge_device_facts__device_id__delete: {
        parameters: {
            query?: {
                /** @description The draft revision you loaded (0 = no draft). */
                draft_revision?: number | null;
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
                    "application/json": components["schemas"]["KnowledgeStateResponse"];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The draft changed since draft_revision */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an approved point/device, or a secret */
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
    create_document_api_v1_sites__site_id__knowledge_documents_post: {
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
                "application/json": components["schemas"]["DocumentRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentCreatedResponse"];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The draft changed since draft_revision */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an approved point/device, or a secret */
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
    update_document_api_v1_sites__site_id__knowledge_documents__document_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                document_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DocumentRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeStateResponse"];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The draft changed since draft_revision */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an approved point/device, or a secret */
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
    delete_document_api_v1_sites__site_id__knowledge_documents__document_id__delete: {
        parameters: {
            query?: {
                /** @description The draft revision you loaded (0 = no draft). */
                draft_revision?: number | null;
            };
            header?: never;
            path: {
                site_id: number;
                document_id: string;
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
                    "application/json": components["schemas"]["KnowledgeStateResponse"];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The draft changed since draft_revision */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an approved point/device, or a secret */
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
    discard_draft_api_v1_sites__site_id__knowledge_draft_delete: {
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
                    "application/json": components["schemas"]["KnowledgeStateResponse"];
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
            /** @description Not onboarded, or no such item */
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
    revert_draft_items_api_v1_sites__site_id__knowledge_draft_revert_post: {
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
                "application/json": components["schemas"]["RevertRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeStateResponse"];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The draft changed since draft_revision */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an approved point/device, or a secret */
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
    put_point_guide_api_v1_sites__site_id__knowledge_point_guides__device_id___point_name__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                device_id: number;
                point_name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PointGuideRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeStateResponse"];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The draft changed since draft_revision */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an approved point/device, or a secret */
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
    delete_point_guide_api_v1_sites__site_id__knowledge_point_guides__device_id___point_name__delete: {
        parameters: {
            query?: {
                /** @description The draft revision you loaded (0 = no draft). */
                draft_revision?: number | null;
            };
            header?: never;
            path: {
                site_id: number;
                device_id: number;
                point_name: string;
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
                    "application/json": components["schemas"]["KnowledgeStateResponse"];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The draft changed since draft_revision */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an approved point/device, or a secret */
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
    publish_api_v1_sites__site_id__knowledge_publish_post: {
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
                "application/json": components["schemas"]["PublishRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeVersion"];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The draft changed since draft_revision */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Nothing to publish */
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
    create_site_prompt_api_v1_sites__site_id__knowledge_site_prompts_post: {
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
                "application/json": components["schemas"]["SitePromptRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SitePromptCreatedResponse"];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The draft changed since draft_revision */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an approved point/device, or a secret */
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
    update_site_prompt_api_v1_sites__site_id__knowledge_site_prompts__prompt_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                prompt_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SitePromptRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeStateResponse"];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The draft changed since draft_revision */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an approved point/device, or a secret */
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
    delete_site_prompt_api_v1_sites__site_id__knowledge_site_prompts__prompt_id__delete: {
        parameters: {
            query?: {
                /** @description The draft revision you loaded (0 = no draft). */
                draft_revision?: number | null;
            };
            header?: never;
            path: {
                site_id: number;
                prompt_id: string;
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
                    "application/json": components["schemas"]["KnowledgeStateResponse"];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The draft changed since draft_revision */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not an approved point/device, or a secret */
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
    list_versions_api_v1_sites__site_id__knowledge_versions_get: {
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
                    "application/json": components["schemas"]["KnowledgeVersionSummary"][];
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
            /** @description Not onboarded, or no such item */
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
    delete_versions_api_v1_sites__site_id__knowledge_versions_delete: {
        parameters: {
            query: {
                /** @description Repeat for each version. */
                version: number[];
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
                    "application/json": components["schemas"]["KnowledgeVersionSummary"][];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description One of them is the version the AI uses */
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
    get_version_api_v1_sites__site_id__knowledge_versions__version__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                version: number;
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
                    "application/json": components["schemas"]["KnowledgeVersion"];
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
            /** @description Not onboarded, or no such item */
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
    restore_version_api_v1_sites__site_id__knowledge_versions__version__restore_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                site_id: number;
                version: number;
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
                    "application/json": components["schemas"]["KnowledgeVersion"];
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
            /** @description Not onboarded, or no such item */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description There is a draft: publish or discard it */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description That version is already in use */
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
    get_site_profile_api_v1_sites__site_id__profile_get: {
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
                    "application/json": components["schemas"]["ProfileVersion"];
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
            /** @description Not synced or not onboarded yet */
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
    approve_site_profile_changes_api_v1_sites__site_id__profile_approve_post: {
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
                "application/json": components["schemas"]["ApproveChangesRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileVersion"];
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
            /** @description Not synced or not onboarded yet */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description backend-ot was read again since */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unknown change id, or nothing to approve */
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
    get_pending_changes_api_v1_sites__site_id__profile_changes_get: {
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
                    "application/json": components["schemas"]["PendingChanges"];
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
            /** @description Not synced or not onboarded yet */
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
    sync_site_profile_api_v1_sites__site_id__profile_sync_post: {
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
                    "application/json": components["schemas"]["PendingChanges"];
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
            /** @description Not synced or not onboarded yet */
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
            /** @description backend-ot unreachable */
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
    list_site_profile_versions_api_v1_sites__site_id__profile_versions_get: {
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
                    "application/json": components["schemas"]["ProfileVersionSummary"][];
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
            /** @description Not synced or not onboarded yet */
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
