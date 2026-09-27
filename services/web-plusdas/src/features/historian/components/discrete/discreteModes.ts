// How enum and bitfield selections are drawn. Each mode lives in its own file in this folder;
// to drop one, delete its file(s), remove its entry here, and remove its branch in TrendChart
// (typecheck points at it). The toggle hides itself once only one mode is left.
export const DISCRETE_MODES = [
  { id: 'lanes', label: 'State lanes' },   // StateLanes.tsx + stateSegments.ts
  { id: 'steps', label: 'Step lines' },    // stepSeries.tsx
] as const;

export type DiscreteModeId = (typeof DISCRETE_MODES)[number]['id'];

export const DEFAULT_DISCRETE_MODE: DiscreteModeId = DISCRETE_MODES[0].id;

export function isDiscreteModeId(value: unknown): value is DiscreteModeId {
  return DISCRETE_MODES.some(mode => mode.id === value);
}
