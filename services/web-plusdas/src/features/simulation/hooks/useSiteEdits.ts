import { useState } from "react";
import type { SiteConfig } from "@/api/types/powerflow";
import { editsFromConfig, hasChanges, type SiteEdits } from "../lib/siteEdits";

/** The editable settings of a stored site. A newer `config` (a refetch) replaces them only while
 * nothing is unsaved, so a refetch never wipes a pick the user hasn't saved yet. */
export function useSiteEdits(config: SiteConfig) {
  const [edits, setEdits] = useState<SiteEdits>(() => editsFromConfig(config));
  const [base, setBase] = useState(config);
  if (config !== base) {
    // Adjusting state while rendering: React re-renders at once with the synced values.
    setBase(config);
    if (!hasChanges(base, edits)) setEdits(editsFromConfig(config));
  }
  const reset = () => setEdits(editsFromConfig(config));
  return { edits, setEdits, reset, dirty: hasChanges(config, edits) };
}
