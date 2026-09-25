import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Building2,
  Activity,
  BarChart3,
  PlayCircle,
  FileText,
  Bot,
  Users,
  Settings,
  Search,
  ChevronLeft,
  ChevronRight,
  LogOut,
  StickyNote,
  Radio,
} from "lucide-react";
import { useAuth } from "@/shared/contexts/auth";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ModeToggle } from "@/shared/components/mode-toggle";

const navigationItems = [
  {
    id: 'sites',
    title: 'Sites',
    icon: Building2,
    path: '/sites',
    roles: ['engineer', 'admin', 'monitor']
  },
  {
    id: 'health',
    title: 'Health',
    icon: Activity,
    path: '/health',
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
    id: 'narrative',
    title: 'Narrative',
    icon: PlayCircle,
    path: '/narrative',
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

export function AppSidebar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const visibleItems = navigationItems.filter(item =>
    user && item.roles.includes(user.role)
  );

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className={cn(
      "flex flex-col h-screen bg-sidebar border-r border-sidebar-border transition-all duration-300",
      isCollapsed ? "w-16" : "w-64"
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
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="text-sidebar-foreground hover:bg-sidebar-accent"
          >
            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </Button>
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

      <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
        {visibleItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path);

          return (
            <NavLink
              key={item.id}
              to={item.path}
              className={cn(
                "flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200",
                "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                active
                  ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-industrial"
                  : "text-sidebar-foreground"
              )}
            >
              <Icon className={cn("w-5 h-5", !isCollapsed && "mr-3")} />
              {!isCollapsed && <span>{item.title}</span>}
            </NavLink>
          );
        })}
      </nav>

      {user && (
        <div className="p-4 border-t border-sidebar-border flex-shrink-0 mt-auto">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gradient-secondary rounded-full flex items-center justify-center">
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
