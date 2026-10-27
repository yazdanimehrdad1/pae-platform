import { defineConfig } from "@playwright/test";

// Layout checks (`make test-layout`): every page at phone, tablet and laptop widths against a
// running UI (the Vite dev server by default, `make run`), with the dev stack up and seeded.
export default defineConfig({
  testDir: "tests/layout",
  outputDir: "test-results/layout",
  fullyParallel: true,
  reporter: [["list"]],
  use: {
    baseURL: process.env.LAYOUT_BASE_URL ?? "http://localhost:5174",
    browserName: "chromium",
  },
});
