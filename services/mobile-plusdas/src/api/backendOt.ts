// backend-ot calls the app makes, one function per endpoint. Paths and shapes follow
// contracts/openapi/backend-ot.openapi.json (types in ./types.ts).
import { apiFetch } from "./client";
import type { Health, Site } from "./types";

export const fetchHealth = () => apiFetch<Health>("/api/healthz");

export const fetchSites = () => apiFetch<Site[]>("/api/sites");
