import { useMemo, useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import type { ConditionPointOption } from "./conditionModel";

/** Searchable point picker, grouped by `option.group` (in first-seen order). */
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
  const groups = useMemo(() => {
    const byGroup = new Map<string, ConditionPointOption[]>();
    for (const option of options) byGroup.set(option.group, [...(byGroup.get(option.group) ?? []), option]);
    return [...byGroup];
  }, [options]);
  const selected = options.find(option => option.id === value) ?? null;

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button id={id} variant="outline" role="combobox" aria-label={ariaLabel} aria-labelledby={ariaLabelledBy} aria-expanded={isOpen}
          aria-invalid={invalid} aria-describedby={describedBy} className={cn("w-full justify-between font-normal", className)}>
          <span className="truncate">{selected ? selected.label : placeholder}</span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] min-w-[18rem] p-0" align="start">
        <Command>
          <CommandInput placeholder="Search devices and points" />
          <CommandList>
            <CommandEmpty>No point found.</CommandEmpty>
            {groups.map(([group, groupOptions]) => (
              <CommandGroup key={group} heading={group}>
                {groupOptions.map(option => (
                  <CommandItem key={option.id} value={`${group} ${option.name} ${option.hint ?? ""} ${option.id}`}
                    onSelect={() => { onChange(option.id); setIsOpen(false); }}>
                    <Check className={cn("mr-2 h-4 w-4", option.id === value ? "opacity-100" : "opacity-0")} />
                    {option.name}
                    <span className="ml-auto text-xs text-muted-foreground">
                      {[option.hint, option.unit, option.kind !== "numeric" ? option.kind : null].filter(Boolean).join(" · ")}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
