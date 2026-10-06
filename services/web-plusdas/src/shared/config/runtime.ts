// Runtime configuration: read from window.__APP_CONFIG__, which /config.js sets before the
// app bundle loads (index.html). In the container, /config.js is written at start from the
// environment (docker/40-app-config.sh); in `npm run dev` it is public/config.js. Nothing
// environment-specific is baked into the build, so one image runs everywhere.
// This module is the only reader of window.__APP_CONFIG__.

export interface RuntimeConfig {
  /** Base for every API call. Keep it same-origin (`/api`): see docs/same-origin.md. */
  apiBaseUrl: string;
  /** Base for the powerflow simulator's API (nginx forwards it to powerflow's /api). Same-origin. */
  powerflowBaseUrl: string;
}

const DEFAULTS: RuntimeConfig = {
  apiBaseUrl: '/api',
  powerflowBaseUrl: '/powerflow-api',
};

export function getRuntimeConfig(): RuntimeConfig {
  const injected = typeof window !== 'undefined' ? window.__APP_CONFIG__ : undefined;
  return {
    // An empty value (unset env var at container start) falls back to the default.
    apiBaseUrl: injected?.apiBaseUrl || DEFAULTS.apiBaseUrl,
    powerflowBaseUrl: injected?.powerflowBaseUrl || DEFAULTS.powerflowBaseUrl,
  };
}
