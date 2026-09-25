import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode: _mode }) => ({
  server: {
    host: "::",
    // `make run` passes --port (RUN_PORT, default 5174); the container owns 5173.
    port: 5174,
    proxy: {
      // Same origin in dev as in the container: the browser calls /api on this server,
      // which forwards to backend-ot (the dev stack's by default). See docs/same-origin.md.
      '/api': {
        target: process.env.WEB_PLUSDAS_DEV_API_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
        // Follow backend slash-redirects server-side so they never reach the
        // browser as a cross-origin request. Dev only — see docs/same-origin.md.
        followRedirects: true,
      },
    },
  },
  plugins: [
    react(),
  ].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      // Types generated from backend-ot's contract (scripts/api-types.mjs). The one import
      // path for API types; on extraction it can point at a published contracts package.
      "@contracts/backend-ot": path.resolve(__dirname, "./src/api/generated/backend-ot.ts"),
    },
  },
}));
