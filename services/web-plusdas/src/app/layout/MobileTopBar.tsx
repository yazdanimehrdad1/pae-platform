import { useState } from "react";
import { NavLink } from "react-router-dom";
import { BarChart3, Bell, BellRing, Menu, StickyNote } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { activeAlarmsText, useActiveAlarms, worstActiveSeverity } from "@/shared/hooks/useActiveAlarms";
import { NavDrawer } from "./AppSidebar";

interface MobileTopBarProps {
  // Opens the notes drawer; omitted on the Notes page itself.
  onOpenNotes?: () => void;
}

// The phone shell: the navigation lives in a drawer behind the menu button, so pages get the
// full width. The alarm bell stays visible here, like in the sidebar.
export function MobileTopBar({ onOpenNotes }: MobileTopBarProps) {
  const [isNavOpen, setIsNavOpen] = useState(false);
  const activeAlarms = useActiveAlarms().data;
  const alarmSeverity = worstActiveSeverity(activeAlarms);
  const alarmText = activeAlarmsText(activeAlarms);
  const AlarmIcon = alarmSeverity ? BellRing : Bell;

  return (
    <header className="flex h-12 shrink-0 items-center gap-1 border-b border-sidebar-border bg-sidebar px-2 print:hidden">
      <Button
        variant="ghost"
        size="icon"
        aria-label="Open navigation"
        onClick={() => setIsNavOpen(true)}
        className="text-sidebar-foreground hover:bg-sidebar-accent"
      >
        <Menu className="h-5 w-5" />
      </Button>
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-primary">
          <BarChart3 className="h-4 w-4 text-white" />
        </div>
        <span className="truncate font-bold text-sidebar-foreground">Industrial Analytics</span>
      </div>
      <NavLink
        to="/alarms"
        aria-label="System alarms"
        title={alarmText ?? "System alarms"}
        data-alarm-severity={alarmSeverity ?? "none"}
        className="rounded-md p-2 text-sidebar-foreground hover:bg-sidebar-accent"
      >
        <AlarmIcon
          className={cn(
            "h-5 w-5",
            alarmSeverity && (alarmSeverity === "fault" ? "text-alarm-fault" : "text-alarm-warning"),
          )}
        />
      </NavLink>
      {onOpenNotes && (
        <Button
          variant="ghost"
          size="icon"
          aria-label="Open notes"
          onClick={onOpenNotes}
          className="text-sidebar-foreground hover:bg-sidebar-accent"
        >
          <StickyNote className="h-5 w-5" />
        </Button>
      )}
      <NavDrawer open={isNavOpen} onOpenChange={setIsNavOpen} />
    </header>
  );
}
