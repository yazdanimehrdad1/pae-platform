import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/shared/contexts/auth";
import { AppSidebar } from "./AppSidebar";
import { Notes } from "@/shared/components/Notes";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { useNotesSidebar } from "@/shared/contexts/NotesSidebarContext";

interface DashboardLayoutProps {
  children: ReactNode;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  const isNotesPage = location.pathname === "/notes";
  const { isNotesCollapsed, setIsNotesCollapsed } = useNotesSidebar();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="h-screen bg-background flex w-full overflow-hidden">
      <AppSidebar />
      <div className="flex-1 flex overflow-hidden">
        <main className="flex-1 overflow-auto">
          {children}
        </main>

        {!isNotesPage && (
          <>
            <div className="relative border-l border-border flex flex-col justify-center">
              <Button
                variant="ghost"
                size="icon"
                className="h-12 w-4 rounded-none rounded-l-md border-y border-l border-border -mr-[1px] z-10 bg-background hover:bg-muted"
                onClick={() => setIsNotesCollapsed(!isNotesCollapsed)}
              >
                {isNotesCollapsed ? <PanelLeftOpen className="h-3 w-3 rotate-180" /> : <PanelLeftClose className="h-3 w-3 rotate-180" />}
              </Button>
            </div>

            <div
              className={`border-l border-border transition-all duration-300 ease-in-out flex flex-col ${
                isNotesCollapsed ? "w-0 opacity-0 overflow-hidden" : "w-80"
              }`}
            >
              <div className="bg-card border border-border rounded-lg p-4 flex flex-col h-full overflow-hidden m-2">
                <Notes />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
