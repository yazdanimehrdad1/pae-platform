/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_RTAC_SERVER_BASE_URL: string;
  readonly VITE_WS_BASE_URL: string;
  readonly VITE_APP_TITLE: string;
  readonly VITE_ENABLE_MOCK_DATA: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.json" {
  const value: any;
  export default value;
}