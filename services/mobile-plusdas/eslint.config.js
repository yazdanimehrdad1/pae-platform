// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require("eslint/config");
const expoConfig = require("eslint-config-expo/flat");

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ["dist/*", ".expo/*", "src/api/generated/*", "expo-env.d.ts"],
  },
  {
    // One-way imports: app -> features -> api / shared. api and shared never import features.
    files: ["src/api/**", "src/shared/**"],
    rules: {
      "no-restricted-imports": ["error", { patterns: ["@/features/*", "**/features/**"] }],
    },
  },
]);
