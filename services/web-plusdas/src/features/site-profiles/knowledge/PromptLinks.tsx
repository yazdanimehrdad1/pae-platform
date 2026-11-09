import { useState } from "react";
import { ChevronDown, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { LINK_KIND_LABELS, LINK_KINDS, type LinkKind, type LinkOption, POINT_SEPARATOR } from "./linkValues";

// The pickers and badges of a site prompt's links (see linkValues.ts).

/** The four pickers of the prompt form. */
export function PromptLinksEditor({ options, values, onChange }: {
  options: Record<LinkKind, LinkOption[]>;
  values: Record<LinkKind, string[]>;
  onChange: (values: Record<LinkKind, string[]>) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Linked to <span className="font-normal text-muted-foreground">(optional: helps the AI find the right data)</span></p>
      <div className="flex flex-wrap gap-2">
        {LINK_KINDS.map(kind => (
          <LinkPicker
            key={kind}
            kind={kind}
            options={options[kind]}
            selected={values[kind]}
            onChange={selected => onChange({ ...values, [kind]: selected })}
          />
        ))}
      </div>
      <LinkBadges options={options} values={values} onRemove={(kind, value) => onChange({ ...values, [kind]: values[kind].filter(entry => entry !== value) })} />
    </div>
  );
}

function LinkPicker({ kind, options, selected, onChange }: {
  kind: LinkKind;
  options: LinkOption[];
  selected: string[];
  onChange: (selected: string[]) => void;
}) {
  const [filter, setFilter] = useState("");
  const needle = filter.trim().toLowerCase();
  const shown = options.filter(option => !needle || option.label.toLowerCase().includes(needle));
  const toggle = (value: string, checked: boolean) =>
    onChange(checked ? [...selected, value] : selected.filter(entry => entry !== value));
  const label = LINK_KIND_LABELS[kind];
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" aria-label={`Link ${label.toLowerCase()}`}>
          {label}{selected.length > 0 ? ` (${selected.length})` : ""}<ChevronDown className="w-4 h-4 ml-1" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 p-2 space-y-2">
        {options.length > 8 && (
          <Input value={filter} onChange={event => setFilter(event.target.value)} placeholder={`Search ${label.toLowerCase()}`} aria-label={`Search ${label.toLowerCase()}`} />
        )}
        {options.length === 0 && <p className="text-sm text-muted-foreground p-1">Nothing to link yet.</p>}
        <ul className="max-h-64 overflow-y-auto space-y-1">
          {shown.map(option => {
            const id = `link-${kind}-${option.value}`;
            return (
              <li key={option.value} className="flex items-start gap-2 rounded px-1 py-0.5 hover:bg-muted">
                <Checkbox id={id} checked={selected.includes(option.value)} onCheckedChange={checked => toggle(option.value, checked === true)} className="mt-0.5" />
                <label htmlFor={id} className="text-sm cursor-pointer">
                  {option.label}
                  {option.detail && <span className="block text-xs text-muted-foreground">{option.detail}</span>}
                </label>
              </li>
            );
          })}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

/** The links as small badges; with `onRemove`, each has a remove button. Unknown values (e.g. a link to something no longer approved) show their raw value. */
export function LinkBadges({ options, values, onRemove }: {
  options: Record<LinkKind, LinkOption[]>;
  values: Record<LinkKind, string[]>;
  onRemove?: (kind: LinkKind, value: string) => void;
}) {
  const entries = LINK_KINDS.flatMap(kind =>
    values[kind].map(value => {
      const option = options[kind].find(entry => entry.value === value);
      return { kind, value, label: option?.label ?? value.replace(POINT_SEPARATOR, " ") };
    }),
  );
  if (entries.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-1" aria-label="Links">
      {entries.map(entry => (
        <li key={`${entry.kind}-${entry.value}`}>
          <Badge variant="outline" className="font-normal gap-1">
            <span className="text-muted-foreground">{LINK_KIND_LABELS[entry.kind]}:</span>{entry.label}
            {onRemove && (
              <button type="button" aria-label={`Remove ${entry.label}`} onClick={() => onRemove(entry.kind, entry.value)}>
                <X className="w-3 h-3" />
              </button>
            )}
          </Badge>
        </li>
      ))}
    </ul>
  );
}
