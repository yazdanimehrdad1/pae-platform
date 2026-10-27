import type { ReactNode } from "react";
import { MonitorSmartphone } from "lucide-react";
import { cn } from "@/lib/utils";
import { useBreakpoint } from "@/shared/hooks/use-mobile";

export const EDIT_ON_LARGER_SCREEN = "Open on a tablet or laptop to edit.";

interface HideOnPhoneProps {
  children: ReactNode;
  // Shown on phones in place of the children; omit to show nothing.
  note?: string;
  className?: string;
}

// Editing tools are view-only on phones: renders its children on tablets and laptops, and on a
// phone only the optional note (e.g. EDIT_ON_LARGER_SCREEN).
export function HideOnPhone({ children, note, className }: HideOnPhoneProps) {
  const breakpoint = useBreakpoint();
  if (breakpoint !== "phone") return <>{children}</>;
  if (!note) return null;
  return (
    <p className={cn("flex items-center gap-2 text-xs text-muted-foreground", className)}>
      <MonitorSmartphone className="h-4 w-4 shrink-0" aria-hidden="true" />
      {note}
    </p>
  );
}
