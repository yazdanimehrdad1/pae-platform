// Single-line diagram mocks. backend-ot has no SLD layout or live SLD data yet
// (docs/backend-gaps.md, "Single-line diagram").
import type { SLDDataInfo, SLDLayout } from '@/features/sld/types';

// Site shown when the page is opened without one.
export const MOCK_SLD_SITE_ID = "site-001";

// Diagram picker options; not wired to anything yet.
export const MOCK_SLD_DIAGRAMS = [
  { value: "main", label: "Main Distribution" },
  { value: "emergency", label: "Emergency System" },
  { value: "solar", label: "Solar Integration" },
];

// Static fixtures, loaded lazily so they stay out of the main bundle.
export async function loadMockSLDLayout(): Promise<SLDLayout> {
  const layoutModule = await import("./sld-layout.json");
  return layoutModule.default as SLDLayout;
}

export async function loadMockSLDData(): Promise<SLDDataInfo> {
  const dataModule = await import("./sld-data.json");
  return dataModule.default as SLDDataInfo;
}
