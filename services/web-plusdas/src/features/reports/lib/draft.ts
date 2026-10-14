import type {
  ReportBlock,
  ReportDefinition,
  ReportRunCreateRequest,
  ReportTemplateRecord,
} from "@/api/types/reports";

// The builder edits a ReportDefinition directly. A point not chosen yet is UNSET_POINT and a site
// function not chosen yet is "" (backend-ot ids start at 1): draftProblems() names them, and the
// draft can't be generated or saved until they are filled in.

export type BlockKind = ReportBlock["kind"];
export const UNSET_POINT = 0;

/** backend-ot's limits on a definition (schemas/reports/definition.py); the UI stops at them. */
export const LIMITS = { blocks: 30, chartSeries: 8, kpiItems: 12, tablePoints: 20, alarmRows: 1000 } as const;

export const BLOCK_KIND_LABELS: Record<BlockKind, string> = {
  text: "Text",
  kpi: "Key figures",
  chart: "Chart",
  point_stats_table: "Statistics table",
  alarm_events_table: "Alarm events",
};

const ID_PREFIX: Record<BlockKind, string> = {
  text: "text", kpi: "kpis", chart: "chart", point_stats_table: "stats", alarm_events_table: "alarms",
};

export function blankDefinition(): ReportDefinition {
  return {
    schema_version: 1,
    window: { kind: "calendar", period: "day", offset: -1 },
    blocks: [{ kind: "text", id: "text_1", title: "Summary", body: "{site_name}, {window_start} to {window_end} ({timezone})." }],
  };
}

/** "chart_3": the kind's prefix and the first number no block uses. */
export function nextBlockId(kind: BlockKind, blocks: ReportBlock[]): string {
  const used = new Set(blocks.map(block => block.id));
  let number = 1;
  while (used.has(`${ID_PREFIX[kind]}_${number}`)) number += 1;
  return `${ID_PREFIX[kind]}_${number}`;
}

export function newBlock(kind: BlockKind, blocks: ReportBlock[]): ReportBlock {
  const id = nextBlockId(kind, blocks);
  const title = BLOCK_KIND_LABELS[kind];
  switch (kind) {
    case "text":
      return { kind, id, title: null, body: "" };
    case "kpi":
      return { kind, id, title, items: [{ source: "point_stat", point_id: UNSET_POINT, stat: "max" }] };
    case "chart":
      return { kind, id, title, style: "line", max_points: 500, series: [{ source: "point", point_id: UNSET_POINT }] };
    case "point_stats_table":
      return { kind, id, title, point_ids: [UNSET_POINT], stats: ["min", "max", "avg", "last"], bucket: "none" };
    case "alarm_events_table":
      return { kind, id, title, severity: null, device_ids: [], limit: 200 };
  }
}

export function moveBlock(blocks: ReportBlock[], index: number, delta: -1 | 1): ReportBlock[] {
  const target = index + delta;
  if (target < 0 || target >= blocks.length) return blocks;
  const moved = [...blocks];
  [moved[index], moved[target]] = [moved[target], moved[index]];
  return moved;
}

/** What still has to be filled in, by block id; empty when the draft can be sent. */
export function draftProblems(definition: ReportDefinition): Map<string, string[]> {
  const problems = new Map<string, string[]>();
  for (const block of definition.blocks) {
    const blockProblems: string[] = [];
    switch (block.kind) {
      case "text":
        if (!block.body.trim()) blockProblems.push("Write the text");
        break;
      case "kpi":
        if (block.items.length === 0) blockProblems.push("Add a figure");
        block.items.forEach((item, index) => {
          if (item.source === "point_stat" && item.point_id === UNSET_POINT) blockProblems.push(`Figure ${index + 1}: choose a point`);
          if (item.source === "site_function" && (!item.function || !item.field)) blockProblems.push(`Figure ${index + 1}: choose a function and a value`);
        });
        break;
      case "chart":
        if (block.series.length === 0) blockProblems.push("Add a series");
        block.series.forEach((series, index) => {
          if (series.source === "point" && series.point_id === UNSET_POINT) blockProblems.push(`Series ${index + 1}: choose a point`);
          if (series.source === "site_function" && !series.function) blockProblems.push(`Series ${index + 1}: choose a function`);
        });
        break;
      case "point_stats_table":
        if (block.point_ids.length === 0 || block.point_ids.includes(UNSET_POINT)) blockProblems.push("Choose every point");
        if ((block.stats ?? []).length === 0) blockProblems.push("Choose at least one statistic");
        break;
      case "alarm_events_table":
        break;
    }
    if (blockProblems.length > 0) problems.set(block.id, blockProblems);
  }
  if (definition.window.kind === "fixed" && Date.parse(definition.window.start_time) >= Date.parse(definition.window.end_time)) {
    problems.set("window", ["The period must end after it starts"]);
  }
  return problems;
}

/** backend-ot's 400 lists problems as "<block id>: <message>"; split them by block. */
export function errorsByBlock(errors: string[], blockIds: string[]): { general: string[]; byBlock: Map<string, string[]> } {
  const ids = new Set(blockIds);
  const byBlock = new Map<string, string[]>();
  const general: string[] = [];
  for (const error of errors) {
    const separator = error.indexOf(": ");
    const blockId = separator > 0 ? error.slice(0, separator) : "";
    if (ids.has(blockId)) byBlock.set(blockId, [...(byBlock.get(blockId) ?? []), error.slice(separator + 2)]);
    else general.push(error);
  }
  return { general, byBlock };
}

/** The `errors` list of backend-ot's 400 response, if the error is one. */
export function validationErrors(error: unknown): string[] {
  const detail = (error as { detail?: { errors?: unknown } } | null)?.detail;
  return Array.isArray(detail?.errors) ? detail.errors.filter((item): item is string => typeof item === "string") : [];
}

const sameJson = (first: unknown, second: unknown) => JSON.stringify(first) === JSON.stringify(second);

/** A template whose sections are unchanged keeps its link (a custom period is only an override);
 * anything else is an ad-hoc report with the definition inline. */
export function runRequest(definition: ReportDefinition, template: ReportTemplateRecord | null, name: string): ReportRunCreateRequest {
  const runName = name.trim() || undefined;
  if (template && sameJson(template.definition.blocks, definition.blocks)) {
    return sameJson(template.definition.window, definition.window)
      ? { template_id: template.id, name: runName }
      : { template_id: template.id, window: definition.window, name: runName };
  }
  return { definition, name: runName };
}
