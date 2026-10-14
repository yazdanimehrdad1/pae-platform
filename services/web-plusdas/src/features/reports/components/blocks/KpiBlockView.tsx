import type { KpiBlockResult } from "@/api/types/reports";
import { formatValue } from "../../lib/format";
import { BlockSection } from "./BlockSection";

export function KpiBlockView({ block }: { block: KpiBlockResult }) {
  return (
    <BlockSection title={block.title} error={block.error}>
      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {(block.items ?? []).map((item, index) => (
          <div key={`${item.label}-${index}`} className="rounded-md bg-muted/50 p-3 print:bg-transparent print:border print:border-neutral-300">
            <dt className="text-xs text-muted-foreground">{item.label}</dt>
            <dd className="mt-1 text-2xl font-semibold tabular-nums">{formatValue(item.value, item.unit)}</dd>
            {item.error && <dd className="mt-1 text-xs text-destructive">{item.error}</dd>}
          </div>
        ))}
      </dl>
    </BlockSection>
  );
}
