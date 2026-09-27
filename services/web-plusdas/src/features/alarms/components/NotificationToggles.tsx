import { Mail, Smartphone } from "lucide-react";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { NotificationChannel, NotificationSettings } from "../types";

const CHANNELS: { channel: NotificationChannel; label: string; Icon: typeof Mail }[] = [
  { channel: "mobile", label: "Mobile", Icon: Smartphone },
  { channel: "email", label: "Email", Icon: Mail },
];

/** Mobile and email notifications of a rule, switched independently (both, either or none). */
export function NotificationToggles({ value, onChange, label }: {
  value: NotificationSettings;
  onChange: (value: NotificationSettings) => void;
  /** Accessible name of the group, e.g. "Notifications for p2_phase_b_overcurrent". */
  label: string;
}) {
  const selected = CHANNELS.filter(({ channel }) => value[channel]).map(({ channel }) => channel);
  return (
    <ToggleGroup
      type="multiple"
      size="sm"
      variant="outline"
      value={selected}
      onValueChange={channels => onChange({ mobile: channels.includes("mobile"), email: channels.includes("email") })}
      aria-label={label}
      className="justify-start"
    >
      {CHANNELS.map(({ channel, label: channelLabel, Icon }) => (
        <ToggleGroupItem key={channel} value={channel} aria-label={channelLabel}
          className="h-7 gap-1 px-2 text-xs text-muted-foreground data-[state=on]:text-foreground">
          <Icon aria-hidden className="h-3.5 w-3.5" />{channelLabel}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
