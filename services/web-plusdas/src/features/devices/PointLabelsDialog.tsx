import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { formatLabels, labelKind, maxKey, parseLabels } from "./lib/pointLabels";

interface LabelRow {
  key: string;
  label: string;
}

function rowsFromText(text: string, dataType: string): LabelRow[] {
  const parsed = parseLabels(text, dataType);
  if (parsed.error !== null || parsed.labels === null) {
    return text.trim() === "" ? [] : [{ key: "", label: text.trim() }];
  }
  return Object.entries(parsed.labels)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([key, label]) => ({ key, label }));
}

// Edit one point's value labels as a code (or bit) -> label table. Applying writes them back to
// the grid cell; the grid's Save sends them with the point's other changes.
export function PointLabelsDialog({ pointName, dataType, text, onApply, onClose }: {
  pointName: string;
  dataType: string;
  text: string;
  onApply: (text: string) => void;
  onClose: () => void;
}) {
  const kind = labelKind(dataType);
  const unit = kind === "bitfield" ? "Bit" : "Code";
  const [rows, setRows] = useState<LabelRow[]>(() => rowsFromText(text, dataType));
  const asText = rows
    .filter((row) => row.key.trim() !== "" || row.label.trim() !== "")
    .map((row) => `${row.key.trim()}=${row.label.trim()}`)
    .join("; ");
  const parsed = parseLabels(asText, dataType);

  const update = (index: number, patch: Partial<LabelRow>) =>
    setRows((current) => current.map((row, position) => (position === index ? { ...row, ...patch } : row)));
  const nextKey = () => {
    const used = rows.map((row) => Number(row.key)).filter((value) => Number.isInteger(value));
    return String(used.length ? Math.max(...used) + 1 : 0);
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{kind === "bitfield" ? "Bit labels" : "Enum labels"}: {pointName || "new point"}</DialogTitle>
          <DialogDescription>
            {kind === "bitfield"
              ? `What each bit of this ${dataType} means (bits 0–${maxKey(dataType)}).`
              : `What each value of this ${dataType} means.`}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <div className="grid grid-cols-[6rem_1fr_2rem] gap-2 text-xs text-muted-foreground">
            <span>{unit}</span>
            <span>Label</span>
          </div>
          {rows.map((row, index) => (
            <div key={index} className="grid grid-cols-[6rem_1fr_2rem] gap-2" data-label-row={index}>
              <Input
                inputMode="numeric"
                aria-label={`${unit} ${index + 1}`}
                value={row.key}
                onChange={(event) => update(index, { key: event.target.value })}
              />
              <Input
                aria-label={`Label ${index + 1}`}
                value={row.label}
                onChange={(event) => update(index, { label: event.target.value })}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Remove ${unit.toLowerCase()} ${row.key || index + 1}`}
                onClick={() => setRows((current) => current.filter((_, position) => position !== index))}
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="gap-1"
            onClick={() => setRows((current) => [...current, { key: nextKey(), label: "" }])}
          >
            <Plus className="w-4 h-4" /> Add {unit.toLowerCase()}
          </Button>
          {parsed.error && (
            <p role="alert" className="text-sm text-destructive">
              {parsed.error}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={parsed.error !== null}
            onClick={() => {
              onApply(formatLabels(parsed.labels));
              onClose();
            }}
          >
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
