import type { KnowledgeState, SiteScriptLinks } from "@/api/types/knowledge";
import type { ProfileVersion } from "@/api/types/siteProfiles";
import { localPointName } from "../lib/changes";

// A site prompt's optional links: the approved points, site functions, documents and device
// ratings it is about. They help the AI connect the prompt with what its tools return.

export const NO_LINKS: SiteScriptLinks = { points: [], functions: [], documents: [], devices: [] };

export type LinkKind = keyof SiteScriptLinks;

export interface LinkOption {
  value: string;
  label: string;
  detail?: string;
}

export const POINT_SEPARATOR = "\u0000";

function pointValue(deviceId: number, pointName: string): string {
  return `${deviceId}${POINT_SEPARATOR}${pointName}`;
}

/** What can be linked: approved points and site functions, the draft's documents, and the devices that have ratings in the draft. */
export function linkOptions(profile: ProfileVersion, state: KnowledgeState): Record<LinkKind, LinkOption[]> {
  const deviceNames = new Map(profile.catalog.devices.map(device => [device.device_id, device.name]));
  const guided = new Set((state.content.point_guides ?? []).map(guide => pointValue(guide.device_id, guide.point_name)));
  return {
    points: profile.catalog.points
      .map(point => {
        const value = pointValue(point.device_id, localPointName(point));
        return { value, label: point.name, detail: guided.has(value) ? "has guide" : undefined };
      })
      .sort((left, right) => left.label.localeCompare(right.label)),
    functions: (profile.catalog.functions ?? [])
      .map(fn => ({ value: fn.name, label: fn.name, detail: fn.summary ?? undefined }))
      .sort((left, right) => left.label.localeCompare(right.label)),
    documents: (state.content.documents ?? [])
      .map(document => ({ value: document.document_id ?? "", label: document.title, detail: document.kind.replace("_", " ") }))
      .sort((left, right) => left.label.localeCompare(right.label)),
    devices: (state.content.device_facts ?? [])
      .map(facts => ({ value: String(facts.device_id), label: deviceNames.get(facts.device_id) ?? `device ${facts.device_id}` }))
      .sort((left, right) => left.label.localeCompare(right.label)),
  };
}

/** The links as picker values (strings), per kind. */
export function linkValues(links: SiteScriptLinks | undefined): Record<LinkKind, string[]> {
  const current = links ?? NO_LINKS;
  return {
    points: (current.points ?? []).map(point => pointValue(point.device_id, point.point_name)),
    functions: [...(current.functions ?? [])],
    documents: [...(current.documents ?? [])],
    devices: (current.devices ?? []).map(String),
  };
}

export function valuesToLinks(values: Record<LinkKind, string[]>): SiteScriptLinks {
  return {
    points: values.points.map(value => {
      const [deviceId, pointName] = value.split(POINT_SEPARATOR);
      return { device_id: Number(deviceId), point_name: pointName };
    }),
    functions: values.functions,
    documents: values.documents,
    devices: values.devices.map(Number),
  };
}

export const LINK_KIND_LABELS: Record<LinkKind, string> = {
  points: "Points",
  functions: "Site functions",
  documents: "Documents",
  devices: "Device ratings",
};

export const LINK_KINDS: LinkKind[] = ["points", "functions", "documents", "devices"];
