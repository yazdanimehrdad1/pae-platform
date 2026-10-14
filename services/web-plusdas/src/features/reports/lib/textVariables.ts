import type { DevicePointsEntry } from "@/api/types/devices";
import type { ReportTextVariables } from "@/api/types/reports";
import type { ConditionPointOption } from "@/shared/components/conditions/conditionModel";

// Variables in a text section, filled in by backend-ot when the report is generated (its
// reports/text_variables.py is the source; the catalog lists them):
//   {site_name}  {window_start} ...      a site variable
//   {device:12.name}                     a field of device 12
//   {point:34.name}  {point:34.max}      a field of point 34, or its statistic over the period
// The builder's Insert menu writes them, so nobody types an id.

const TOKEN = /\{([a-z_]+)(?::(\d+)\.([a-z_]+))?\}/g;

export const siteToken = (name: string) => `{${name}}`;
export const deviceToken = (deviceId: number, field: string) => `{device:${deviceId}.${field}}`;
export const pointToken = (pointId: number, field: string) => `{point:${pointId}.${field}}`;

/** `body` with `token` replacing the selection [start, end), and where the caret goes after it. */
export function insertAt(body: string, token: string, start: number, end: number): { body: string; caret: number } {
  const from = Math.max(0, Math.min(start, body.length));
  const to = Math.max(from, Math.min(end, body.length));
  return { body: body.slice(0, from) + token + body.slice(to), caret: from + token.length };
}

/** What the text will read like: names filled in from the site's devices and points, values the
 * report computes shown as ‹what›. A variable that can't be filled in stays as written. */
export function previewText(body: string, context: {
  siteName: string;
  variables: ReportTextVariables;
  devices: DevicePointsEntry[];
  points: ConditionPointOption[];
}): string {
  const siteDescriptions = new Map((context.variables.site ?? []).map(variable => [variable.name, variable.description]));
  const pointFieldDescriptions = new Map((context.variables.point_fields ?? []).map(variable => [variable.name, variable.description]));
  return body.replace(TOKEN, (token, name: string, itemId?: string, field?: string) => {
    if (itemId === undefined) {
      if (name === "site_name") return context.siteName;
      const description = siteDescriptions.get(name);
      return description ? `‹${description.toLowerCase()}›` : token;
    }
    if (name === "device") {
      const device = context.devices.find(candidate => candidate.deviceId === Number(itemId));
      if (!device) return token;
      if (field === "name") return device.deviceName;
      if (field === "type") return device.deviceType;
      return field ? `‹${device.deviceName} ${field}›` : token;
    }
    if (name === "point") {
      const point = context.points.find(candidate => candidate.id === itemId);
      if (!point || !field) return token;
      if (field === "name") return point.name;
      if (field === "unit") return point.unit ?? "";
      if (field === "device") return point.group;
      return pointFieldDescriptions.has(field) ? `‹${field} of ${point.name}›` : token;
    }
    return token;
  });
}
