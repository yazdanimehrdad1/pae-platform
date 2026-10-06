// The same palette as web-plusdas (services/web-plusdas/src/index.css, its HSL CSS variables
// converted to hex; the source variable is noted on each line). Like web-plusdas, the app uses
// the dark theme by default. Copied, never imported: each service stays self-contained, so keep
// the two in step by hand when web-plusdas's theme changes.
export type Palette = {
  background: string;
  surface: string;
  surfacePressed: string;
  border: string;
  text: string;
  textMuted: string;
  accent: string;
  onAccent: string;
  normal: string;
  fault: string;
  faultSurface: string;
  warning: string;
  warningSurface: string;
};

export const LIGHT: Palette = {
  background: "#EDF0F3", // --background 210 20% 94%
  surface: "#FFFFFF", // --card
  surfacePressed: "#F1F5F9", // --muted
  border: "#E1E7EF", // --border
  text: "#1D2530", // --foreground
  textMuted: "#65758B", // --muted-foreground
  accent: "#0EA472", // --primary 160 84% 35%
  onAccent: "#FFFFFF", // --primary-foreground
  normal: "#65758B", // --muted-foreground
  fault: "#C52020", // --alarm-fault
  faultSurface: "#FBE9E9", // --alarm-fault at 95% lightness
  warning: "#CE8509", // --alarm-warning
  warningSurface: "#FEF2DD", // --alarm-warning at 93% lightness
};

export const DARK: Palette = {
  background: "#0F131A", // --background 215 28% 8%
  surface: "#171D26", // --card
  surfacePressed: "#1D2530", // --muted
  border: "#263140", // --border
  text: "#E7EBEF", // --foreground
  textMuted: "#97A3B4", // --muted-foreground
  accent: "#12D393", // --primary 160 84% 45%
  onAccent: "#0F131A", // --primary-foreground
  normal: "#97A3B4", // --muted-foreground
  fault: "#EF4D4D", // --alarm-fault
  faultSurface: "#391818", // --alarm-fault, darkened
  warning: "#F6A823", // --alarm-warning
  warningSurface: "#392B13", // --alarm-warning, darkened
};

export const SPACE = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 } as const;
export const RADIUS = { sm: 6, md: 10, lg: 14 } as const;
export const FONT = { caption: 12, body: 15, title: 17, heading: 22, hero: 28 } as const;

/** Dark, matching web-plusdas's default theme. LIGHT is kept for a future theme switch. */
export function usePalette(): Palette {
  return DARK;
}
