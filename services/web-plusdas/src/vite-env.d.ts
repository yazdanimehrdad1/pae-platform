/// <reference types="vite/client" />

// No VITE_* variables: configuration is read at runtime from window.__APP_CONFIG__
// (see src/shared/config/runtime.ts), so the bundle is the same in every environment.
interface Window {
  __APP_CONFIG__?: Partial<import('./shared/config/runtime').RuntimeConfig>;
}

declare module "*.json" {
  const value: unknown;
  export default value;
}
