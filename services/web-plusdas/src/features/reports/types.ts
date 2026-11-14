import type { DevicePointsEntry } from "@/api/types/devices";
import type { ReportAlarm, ReportSiteFunction, ReportTextVariables } from "@/api/types/reports";
import type { ConditionPointOption } from "@/shared/components/conditions/conditionModel";

/** What the builder's editors can offer on the site. */
export interface BuilderOptions {
  points: ConditionPointOption[];
  devices: DevicePointsEntry[];
  functions: ReportSiteFunction[];
  /** The site's live alarms, which an alarm events table picks from (from the catalog). */
  alarms: ReportAlarm[];
  /** What a text section can fill in (from the catalog). */
  textVariables: ReportTextVariables;
  siteName: string;
  timeZone: string;
}
