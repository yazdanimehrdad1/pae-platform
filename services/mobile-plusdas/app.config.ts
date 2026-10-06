import type { ExpoConfig } from "expo/config";

// Build-time app identity only. Runtime settings (the backend-ot server URL) are chosen in the
// app's Settings screen and stored on the device; `extra.defaultServerUrl` is just the first value.
//
// The EAS project was created by `eas init` (account mdadyaz); EAS_PROJECT_ID overrides it. The
// bundle ids are placeholders until the Apple/Google app records exist.
const config: ExpoConfig = {
  name: "PAE PlusDAS",
  slug: "mobile-plusdas",
  owner: "mdadyaz",
  scheme: "plusdas",
  version: "0.1.0",
  orientation: "portrait",
  // Dark like web-plusdas (src/shared/theme/tokens.ts); also the native window behind the app.
  userInterfaceStyle: "dark",
  backgroundColor: "#0F131A",
  // The PAE logo (the same artwork as web-plusdas's favicon), as 1024 px PNGs. Android crops
  // icons into circles/squircles, so its foreground is the logo at 62% on the app's dark color.
  icon: "./assets/icon.png",
  ios: {
    bundleIdentifier: process.env.IOS_BUNDLE_ID ?? "com.pae.plusdas",
    supportsTablet: true,
  },
  android: {
    package: process.env.ANDROID_PACKAGE ?? "com.pae.plusdas",
    adaptiveIcon: { foregroundImage: "./assets/adaptive-icon.png", backgroundColor: "#0F131A" },
  },
  plugins: ["expo-router", "expo-status-bar"],
  experiments: { typedRoutes: true },
  extra: {
    // In development the app derives the URL from the dev server's host (serverUrl.ts); this is
    // the fallback for builds without one. backendPort follows the root's port override.
    defaultServerUrl: process.env.DEFAULT_SERVER_URL ?? "http://192.168.1.10:8000",
    backendPort: Number(process.env.BACKEND_OT_HTTP_PORT || 8000),
    // Not a secret; committed so local runs and EAS cloud builds both see it.
    eas: { projectId: process.env.EAS_PROJECT_ID || "f6f29a4b-35a9-4873-994f-8e8fccb05648" },
  },
};

export default config;
