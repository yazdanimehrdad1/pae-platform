export const queryKeys = {
  sites: ["sites"] as const,
  health: (url: string) => ["health", url] as const,
};
