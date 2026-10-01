import { useMemo, useState } from "react";
import { Check, ChevronDown, ChevronRight, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import type { ConditionPointOption } from "./conditionModel";

/**
 * Searchable point picker, grouped by `option.group` (the device) in first-seen order. With an
 * empty search each group is a collapsible header, so a site with many devices stays short: only
 * the selected point's group starts open (or the only group). Typing searches every group.
 */
export function PointCombobox({ options, value, onChange, placeholder = "Choose a point", id, ariaLabel, ariaLabelledBy, invalid, describedBy, className }: {
  options: ConditionPointOption[];
  value: string | null;
  onChange: (pointId: string) => void;
  placeholder?: string;
  id?: string;
  ariaLabel?: string;
  ariaLabelledBy?: string;
  invalid?: boolean;
  describedBy?: string;
  className?: string;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const groups = useMemo(() => {
    const byGroup = new Map<string, ConditionPointOption[]>();
    for (const option of options) byGroup.set(option.group, [...(byGroup.get(option.group) ?? []), option]);
    return [...byGroup];
  }, [options]);
  const selected = options.find(option => option.id === value) ?? null;
  const isSearching = search.trim() !== "";

  const openChange = (open: boolean) => {
    if (open) {
      setSearch("");
      setExpandedGroups(new Set(groups.length === 1 ? [groups[0][0]] : selected ? [selected.group] : []));
    }
    setIsOpen(open);
  };
  const toggleGroup = (group: string) => setExpandedGroups(previous => {
    const next = new Set(previous);
    if (next.has(group)) next.delete(group); else next.add(group);
    return next;
  });

  const renderItem = (group: string, option: ConditionPointOption) => (
    <CommandItem key={option.id} value={`${group} ${option.name} ${option.hint ?? ""} ${option.id}`}
      onSelect={() => { onChange(option.id); setIsOpen(false); }}>
      <Check className={cn("mr-2 h-4 w-4", option.id === value ? "opacity-100" : "opacity-0")} />
      {option.name}
      <span className="ml-auto text-xs text-muted-foreground">
        {[option.hint, option.unit, option.kind !== "numeric" ? option.kind : null].filter(Boolean).join(" · ")}
      </span>
    </CommandItem>
  );

  return (
    <Popover open={isOpen} onOpenChange={openChange}>
      <PopoverTrigger asChild>
        <Button id={id} variant="outline" role="combobox" aria-label={ariaLabel} aria-labelledby={ariaLabelledBy} aria-expanded={isOpen}
          aria-invalid={invalid} aria-describedby={describedBy} className={cn("w-full justify-between font-normal", className)}>
          <span className="truncate">{selected ? selected.label : placeholder}</span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] min-w-[18rem] p-0" align="start">
        <Command>
          <CommandInput placeholder="Search devices and points" value={search} onValueChange={setSearch} />
          <CommandList>
            {isSearching && <CommandEmpty>No point found.</CommandEmpty>}
            {isSearching
              ? groups.map(([group, groupOptions]) => (
                <CommandGroup key={group} heading={group}>
                  {groupOptions.map(option => renderItem(group, option))}
                </CommandGroup>
              ))
              : groups.map(([group, groupOptions]) => {
                const isExpanded = expandedGroups.has(group);
                return (
                  <div key={group} className="px-1">
                    <button
                      type="button"
                      className="flex w-full items-center gap-1 rounded-sm px-2 py-1.5 text-left text-xs font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                      aria-expanded={isExpanded}
                      onClick={() => toggleGroup(group)}
                    >
                      {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                      <span className="truncate">{group}</span>
                      <span className="ml-auto tabular-nums">{groupOptions.length}</span>
                    </button>
                    {isExpanded && (
                      <CommandGroup className="p-0 pl-3">
                        {groupOptions.map(option => renderItem(group, option))}
                      </CommandGroup>
                    )}
                  </div>
                );
              })}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
