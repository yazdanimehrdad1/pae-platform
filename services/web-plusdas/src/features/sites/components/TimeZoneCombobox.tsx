import { useMemo, useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { BROWSER_TIME_ZONE } from "@/shared/hooks/useDisplayTimeZone";
import { timeZoneGroups, utcOffset } from "../lib/timeZones";

/** Every supported time zone, grouped by region with its current UTC offset; type to search by
 * zone, city or offset ("berlin", "+05:30"). */
export function TimeZoneCombobox({ id, value, onChange, invalid }: {
  id?: string;
  value: string;
  onChange: (zone: string) => void;
  invalid?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(false);
  // Built when opened, so the offsets are the current ones.
  const groups = useMemo(() => (isOpen ? timeZoneGroups(value ? [value] : []) : []), [isOpen, value]);

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id} type="button" variant="outline" role="combobox" aria-expanded={isOpen} aria-invalid={invalid}
          className={cn("w-full justify-between font-normal", invalid && "border-destructive")}
        >
          {value ? <span>{value} <span className="text-muted-foreground">({utcOffset(value)})</span></span> : <span className="text-muted-foreground">Choose a time zone</span>}
          <ChevronsUpDown aria-hidden className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] min-w-[22rem] p-0" align="start">
        <Command>
          <CommandInput placeholder="Search a city, zone or offset" />
          <CommandList className="max-h-72">
            <CommandEmpty>No time zone matches.</CommandEmpty>
            {groups.map(group => (
              <CommandGroup key={group.region} heading={group.region}>
                {group.zones.map(option => (
                  <CommandItem
                    key={option.zone}
                    value={`${option.zone} ${option.city} ${option.offset}`}
                    onSelect={() => { onChange(option.zone); setIsOpen(false); }}
                  >
                    <Check aria-hidden className={cn("mr-2 h-4 w-4", option.zone === value ? "opacity-100" : "opacity-0")} />
                    {option.zone}
                    {option.zone === BROWSER_TIME_ZONE && <span className="ml-2 text-xs text-muted-foreground">your zone</span>}
                    <span className="ml-auto text-xs tabular-nums text-muted-foreground">{option.offset}</span>
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
