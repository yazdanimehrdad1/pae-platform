import type {
  AutoDispatchBessSettings,
  AutoDispatchDirection,
  AutoDispatchReport,
  AutoDispatchRequest,
} from "@/api/types/powerflow";

// The auto dispatch form: numbers are kept as typed text, and a blank field means "not set"
// (an override falls back to the defaults, a default to powerflow's built-in value).

export const SETTING_FIELDS = ["discharge_pct", "charge_pct", "soc_low_pct", "soc_high_pct", "rest_s", "p_noise_std_pct", "ramp_kw_per_s", "q_kvar"] as const;
export type SettingField = (typeof SETTING_FIELDS)[number];

export type StartChoice = "auto" | AutoDispatchDirection;

export interface SettingsDraft {
  values: Record<SettingField, string>;
  start: StartChoice;
  included: boolean; // only used for a BESS row
}

export interface AutoDispatchDraft {
  defaults: SettingsDraft;
  bess: Record<string, SettingsDraft>;
}

// powerflow's built-in share of the rating, where neither the defaults nor a BESS set one.
export const DEFAULT_POWER_PCT = 50;
const POWER_FIELDS: readonly SettingField[] = ["discharge_pct", "charge_pct"];

function settingsDraft(settings: AutoDispatchBessSettings | undefined): SettingsDraft {
  const values = Object.fromEntries(
    SETTING_FIELDS.map((field) => [field, settings?.[field] != null ? String(settings[field]) : ""]),
  ) as Record<SettingField, string>;
  return { values, start: settings?.start_direction ?? "auto", included: settings?.included !== false };
}

/** The form as powerflow has it now (for every BESS of the site). */
export function draftFromReport(report: AutoDispatchReport | undefined, bessIds: string[]): AutoDispatchDraft {
  const defaults = settingsDraft(report?.defaults);
  // A run started with a site-wide power_pct only: show it as the default shares.
  if (report?.power_pct != null && report.power_pct !== DEFAULT_POWER_PCT) {
    for (const field of POWER_FIELDS) {
      if (defaults.values[field] === "") defaults.values[field] = String(report.power_pct);
    }
  }
  return {
    defaults,
    bess: Object.fromEntries(bessIds.map((id) => [id, settingsDraft(report?.bess_overrides?.[id])])),
  };
}

function toSettings(draft: SettingsDraft, isBess: boolean): AutoDispatchBessSettings {
  const settings: AutoDispatchBessSettings = {};
  for (const field of SETTING_FIELDS) {
    if (draft.values[field].trim() !== "") settings[field] = Number(draft.values[field]);
  }
  if (draft.start !== "auto") settings.start_direction = draft.start;
  if (isBess && !draft.included) settings.included = false;
  return settings;
}

/** The PUT body; a BESS with nothing set is left out (it follows the defaults). */
export function requestFromDraft(draft: AutoDispatchDraft, enabled: boolean): AutoDispatchRequest {
  const bess = Object.fromEntries(
    Object.entries(draft.bess)
      .map(([id, settings]) => [id, toSettings(settings, true)] as const)
      .filter(([, settings]) => Object.keys(settings).length > 0),
  );
  return { enabled, power_pct: DEFAULT_POWER_PCT, defaults: toSettings(draft.defaults, false), bess };
}

function isFieldValid(field: SettingField, text: string): boolean {
  if (text.trim() === "") return true;
  const value = Number(text);
  if (!Number.isFinite(value)) return false;
  return !POWER_FIELDS.includes(field) || (value > 0 && value <= 100);
}

/** Every typed number is a number, and the discharge/charge shares are within (0, 100]. */
export function isDraftValid(draft: AutoDispatchDraft): boolean {
  return [draft.defaults, ...Object.values(draft.bess)].every((settings) =>
    SETTING_FIELDS.every((field) => isFieldValid(field, settings.values[field])),
  );
}
