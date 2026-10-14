import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";
import type { ReportBlock } from "@/api/types/reports";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { BLOCK_KIND_LABELS } from "../../lib/draft";
import type { BuilderOptions } from "../../types";
import { AlarmEventsTableEditor, ChartEditor, KpiEditor, PointStatsTableEditor } from "./BlockEditors";
import { TextEditor } from "./TextEditor";

/** One section of the report: its title, its order, its settings, and what is wrong with it. */
export function BlockEditor({ block, position, count, options, problems, onChange, onMove, onRemove }: {
  block: ReportBlock;
  position: number;
  count: number;
  options: BuilderOptions;
  problems: string[];
  onChange: (block: ReportBlock) => void;
  onMove: (delta: -1 | 1) => void;
  onRemove: () => void;
}) {
  const label = BLOCK_KIND_LABELS[block.kind];
  return (
    <section aria-label={`Section ${position + 1}: ${label}`} className="space-y-3 rounded-lg border border-border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{label}</Badge>
        <Input
          aria-label={`Section ${position + 1} title`} placeholder="Title (optional)" className="max-w-sm" maxLength={200}
          value={block.title ?? ""} onChange={event => onChange({ ...block, title: event.target.value || null })}
        />
        <div className="ml-auto flex gap-1">
          <Button type="button" size="icon" variant="ghost" className="h-8 w-8" disabled={position === 0} onClick={() => onMove(-1)} aria-label={`Move section ${position + 1} up`}>
            <ArrowUp aria-hidden className="h-4 w-4" />
          </Button>
          <Button type="button" size="icon" variant="ghost" className="h-8 w-8" disabled={position === count - 1} onClick={() => onMove(1)} aria-label={`Move section ${position + 1} down`}>
            <ArrowDown aria-hidden className="h-4 w-4" />
          </Button>
          <Button type="button" size="icon" variant="ghost" className="h-8 w-8" disabled={count === 1} onClick={onRemove} aria-label={`Remove section ${position + 1}`}>
            <Trash2 aria-hidden className="h-4 w-4" />
          </Button>
        </div>
      </div>
      {block.kind === "text" && <TextEditor block={block} options={options} onChange={onChange} />}
      {block.kind === "kpi" && <KpiEditor block={block} options={options} onChange={onChange} />}
      {block.kind === "chart" && <ChartEditor block={block} options={options} onChange={onChange} />}
      {block.kind === "point_stats_table" && <PointStatsTableEditor block={block} options={options} onChange={onChange} />}
      {block.kind === "alarm_events_table" && <AlarmEventsTableEditor block={block} options={options} onChange={onChange} />}
      {problems.length > 0 && (
        <ul className="space-y-1" aria-label={`Section ${position + 1} problems`}>
          {problems.map(problem => <li key={problem} className="text-sm text-destructive">{problem}</li>)}
        </ul>
      )}
    </section>
  );
}
