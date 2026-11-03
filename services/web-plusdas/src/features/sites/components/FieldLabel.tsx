import type { ReactNode } from "react";
import { Label } from "@/components/ui/label";

export type FieldMarker = "required" | "recommended";

const MARKS: Record<FieldMarker, { symbol: string; title: string; className: string }> = {
  required: { symbol: "*", title: "Required", className: "text-destructive" },
  recommended: { symbol: "†", title: "Recommended", className: "text-primary" },
};

// A form label with its marker beside it, outside the <label>: the field's accessible name
// stays the plain label, and the form's FieldMarkerLegend says what the marks mean.
export function FieldLabel({ htmlFor, marker, children }: {
  htmlFor?: string;
  marker?: FieldMarker;
  children: ReactNode;
}) {
  const mark = marker ? MARKS[marker] : null;
  return (
    <div className="flex items-baseline gap-0.5">
      <Label htmlFor={htmlFor}>{children}</Label>
      {mark && <span aria-hidden="true" title={mark.title} className={`text-sm font-medium ${mark.className}`}>{mark.symbol}</span>}
    </div>
  );
}

export function FieldMarkerLegend({ markers }: { markers: FieldMarker[] }) {
  return (
    <p className="text-xs text-muted-foreground">
      {markers.map((marker, index) => (
        <span key={marker}>
          {index > 0 && " · "}
          <span aria-hidden="true" className={MARKS[marker].className}>{MARKS[marker].symbol}</span> <span>{MARKS[marker].title}</span>
        </span>
      ))}
    </p>
  );
}
