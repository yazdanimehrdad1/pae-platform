import type { TextBlockResult } from "@/api/types/reports";
import { BlockSection } from "./BlockSection";

export function TextBlockView({ block }: { block: TextBlockResult }) {
  return (
    <BlockSection title={block.title} error={block.error}>
      <p className="whitespace-pre-wrap text-sm leading-relaxed">{block.body}</p>
    </BlockSection>
  );
}
