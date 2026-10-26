import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Building2,
  Bell,
  BellRing,
  BarChart3,
  FileText,
  Bot,
  Cpu,
  Gauge,
  Users,
  Settings,
  Search,
  ChevronLeft,
  ChevronRight,
  LogOut,
  StickyNote,
  Radio,
  ExternalLink,
  type LucideIcon,
} from "lucide-react";
import { useAuth } from "@/shared/contexts/auth";
import { activeAlarmsText, useActiveAlarms, worstActiveSeverity } from "@/shared/hooks/useActiveAlarms";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ModeToggle } from "@/shared/components/mode-toggle";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useBreakpoint } from "@/shared/hooks/use-mobile";

interface NavigationItem {
  id: string;
  title: string;
  icon: LucideIcon;
  path: string;
  roles: string[];
  newTabOption?: boolean; // also offers a button that opens it in a new browser tab
}

const navigationItems: NavigationItem[] = [
  {
    id: 'sites',
    title: 'Sites',
    icon: Building2,
    path: '/sites',
    roles: ['engineer', 'admin', 'monitor']
  },
  {
    id: 'alarms',
    title: 'System alarms',
    icon: Bell, // rings in the alarm color while any site has an active alarm (see AppSidebar)
    path: '/alarms',
    roles: ['monitor', 'admin', 'engineer']
  },
  {
    id: 'historian',
    title: 'Historian',
    icon: BarChart3,
    path: '/historian',
    roles: ['engineer', 'admin']
  },
  {
    id: 'live-data',
    title: 'Live Data',
    icon: Radio,
    path: '/live-data',
    roles: ['engineer', 'admin', 'monitor']
  },
  {
    id: 'reports',
    title: 'Reports',
    icon: FileText,
    path: '/reports',
    roles: ['engineer', 'admin', 'monitor']
  },
  {
    id: 'task-builder',
    title: 'AI Tasks',
    icon: Bot,
    path: '/task-builder',
    roles: ['engineer']
  },
  {
    id: 'simulation',
    title: 'Simulation',
    icon: Cpu,
    path: '/simulation',
    roles: ['engineer', 'admin'],
    newTabOption: true,
  },
  {
    id: 'optimization',
    title: 'Optimization',
    icon: Gauge,
    path: '/optimization',
    roles: ['engineer', 'admin']
  },
  {
    id: 'users',
    title: 'Users',
    icon: Users,
    path: '/users',
    roles: ['admin']
  },
  {
    id: 'notes',
    title: 'Notes',
    icon: StickyNote,
    path: '/notes',
    roles: ['engineer', 'admin', 'monitor']
  },
  {
    id: 'settings',
    title: 'Settings',
    icon: Settings,
    path: '/settings',
    roles: ['engineer', 'admin', 'monitor']
  },
];

const NAV_COLLAPSED_STORAGE_KEY = "nav_sidebar_collapsed";

function readSavedCollapsed(): boolean {
  try {
    return localStorage.getItem(NAV_COLLAPSED_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

interface SidebarPanelProps {
  isCollapsed: boolean;
  // The header chevron: collapses the column on laptops, opens the drawer from the tablet rail.
  onToggleCollapse?: () => void;
  // Called after a link is followed (closes the drawer).
  onNavigate?: () => void;
  className?: string;
}

// The navigation itself, rendered as the laptop column, the tablet icon rail or inside the drawer.
function SidebarPanel({ isCollapsed, onToggleCollapse, onNavigate, className }: SidebarPanelProps) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [searchQuery, setSearchQuery] = useState('');

  const visibleItems = navigationItems.filter(item =>
    user && item.roles.includes(user.role)
  );

  const isActive = (path: string) => location.pathname === path;

  // The System alarms bell: red while any site has an active fault, amber while only warnings.
  const activeAlarms = useActiveAlarms().data;
  const alarmSeverity = worstActiveSeverity(activeAlarms);
  const alarmText = activeAlarmsText(activeAlarms);

  return (
    <div className={cn(
      "flex flex-col h-full bg-sidebar border-r border-sidebar-border transition-all duration-300 print:hidden",
      className
    )}>
      <div className={cn(
        "flex border-b border-sidebar-border transition-all duration-300 flex-shrink-0",
        isCollapsed ? "flex-col items-center justify-center p-2 gap-4" : "flex-row items-center justify-between p-4"
      )}>
        {!isCollapsed && (
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-white" />
            </div>
            <div className="font-bold text-sidebar-foreground">
              Industrial Analytics
            </div>
          </div>
        )}
        <div className={cn("flex items-center", isCollapsed ? "flex-col space-y-2" : "space-x-1")}>
          <ModeToggle />
          {onToggleCollapse && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onToggleCollapse}
              aria-label={isCollapsed ? "Expand navigation" : "Collapse navigation"}
              className="text-sidebar-foreground hover:bg-sidebar-accent"
            >
              {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
            </Button>
          )}
        </div>
      </div>

      {!isCollapsed && (
        <div className="p-4 border-b border-sidebar-border flex-shrink-0">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-sidebar-foreground/60" />
            <Input
              placeholder="Ask AI Assistant..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 bg-sidebar-accent border-sidebar-border text-sidebar-foreground placeholder:text-sidebar-foreground/60"
            />
          </div>
        </div>
      )}

      <nav className={cn("flex-1 space-y-2 overflow-y-auto", isCollapsed ? "p-2" : "p-4")}>
        {visibleItems.map((item) => {
          const active = isActive(item.path);
          const alarming = item.id === 'alarms' && alarmSeverity !== null;
          const Icon = alarming ? BellRing : item.icon;

          const link = (
            <NavLink
              key={item.id}
              to={item.path}
              onClick={onNavigate}
              // Collapsed, only the icon shows: its title is the tooltip and the accessible name.
              title={alarming ? alarmText ?? undefined : isCollapsed ? item.title : undefined}
              aria-label={isCollapsed ? item.title : undefined}
              data-alarm-severity={item.id === 'alarms' ? alarmSeverity ?? 'none' : undefined}
              className={cn(
                "flex items-center rounded-lg py-2 text-sm font-medium transition-all duration-200",
                isCollapsed ? "justify-center px-0" : "px-3",
                "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                active
                  ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-industrial"
                  : "text-sidebar-foreground"
              )}
            >
              <Icon
                className={cn(
                  "w-5 h-5",
                  !isCollapsed && "mr-3",
                  alarming && (alarmSeverity === 'fault' ? "text-alarm-fault" : "text-alarm-warning")
                )}
              />
              {!isCollapsed && <span>{item.title}</span>}
            </NavLink>
          );
          if (!item.newTabOption || isCollapsed) return link;
          // The item opens in this tab; the icon next to it opens it in a new one.
          return (
            <div key={item.id} className="relative">
              {link}
              <a
                href={item.path}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Open ${item.title} in a new tab`}
                title={`Open ${item.title} in a new tab`}
                className={cn(
                  "absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 opacity-60 hover:opacity-100",
                  "hover:bg-sidebar-accent",
                  active ? "text-sidebar-primary-foreground" : "text-sidebar-foreground"
                )}
              >
                <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
              </a>
            </div>
          );
        })}
      </nav>

      {user && (
        <div className={cn("border-t border-sidebar-border flex-shrink-0 mt-auto", isCollapsed ? "p-2" : "p-4")}>
          <div className={cn("flex items-center", isCollapsed ? "flex-col space-y-2" : "space-x-3")}>
            <div
              className="w-8 h-8 shrink-0 bg-gradient-secondary rounded-full flex items-center justify-center"
              title={isCollapsed ? user.name : undefined}
            >
              <span className="text-xs font-medium text-white">
                {user.name.charAt(0).toUpperCase()}
              </span>
            </div>
            {!isCollapsed && (
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-sidebar-foreground truncate">
                  {user.name}
                </div>
                <div className="text-xs text-sidebar-foreground/60 capitalize">
                  {user.role}
                </div>
              </div>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={logout}
              className="text-sidebar-foreground hover:bg-destructive hover:text-destructive-foreground"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

interface NavDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// The full navigation as an overlay from the left (the tablet rail's chevron, the phone top bar's menu).
export function NavDrawer({ open, onOpenChange }: NavDrawerProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="left"
        aria-describedby={undefined}
        // The panel's own chevron closes it, so the sheet's corner X (its last child) is hidden.
        className="w-64 p-0 sm:max-w-xs [&>button:last-child]:hidden"
      >
        <SheetTitle className="sr-only">Navigation</SheetTitle>
        <SidebarPanel
          isCollapsed={false}
          onToggleCollapse={() => onOpenChange(false)}
          onNavigate={() => onOpenChange(false)}
          className="border-r-0"
        />
      </SheetContent>
    </Sheet>
  );
}

// Laptop: the column (collapsible, remembered per browser). Tablet: the icon rail, whose chevron
// opens the full navigation as a drawer so the page keeps its width. Phone: nothing here; the
// top bar (MobileTopBar) opens the drawer.
export function AppSidebar() {
  const breakpoint = useBreakpoint();
  const [isCollapsed, setIsCollapsed] = useState(readSavedCollapsed);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(NAV_COLLAPSED_STORAGE_KEY, String(isCollapsed));
    } catch {
      // Storage blocked: the column starts expanded next time.
    }
  }, [isCollapsed]);

  // Leaving the tablet layout closes its drawer.
  useEffect(() => {
    if (breakpoint !== "tablet") setIsDrawerOpen(false);
  }, [breakpoint]);

  if (breakpoint === "phone") return null;

  if (breakpoint === "tablet") {
    return (
      <>
        <SidebarPanel isCollapsed onToggleCollapse={() => setIsDrawerOpen(true)} className="w-16 shrink-0" />
        <NavDrawer open={isDrawerOpen} onOpenChange={setIsDrawerOpen} />
      </>
    );
  }

  return (
    <SidebarPanel
      isCollapsed={isCollapsed}
      onToggleCollapse={() => setIsCollapsed(!isCollapsed)}
      className={cn("shrink-0", isCollapsed ? "w-16" : "w-64")}
    />
  );
}
