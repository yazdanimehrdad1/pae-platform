import { ReactNode, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/shared/contexts/auth";
import { AppSidebar } from "./AppSidebar";
import { MobileTopBar } from "./MobileTopBar";
import { Notes } from "@/features/notes/components/Notes";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Loader2 } from "lucide-react";
import { useNotesSidebar } from "@/shared/contexts/NotesSidebarContext";
import { useBreakpoint } from "@/shared/hooks/use-mobile";

interface DashboardLayoutProps {
  children: ReactNode;
}

// The shell per breakpoint (see useBreakpoint):
// - laptop: navigation column + page + Notes column (both collapsible, remembered);
// - tablet: navigation icon rail + page; Notes opens as a drawer from the edge handle;
// - phone: top bar (menu, alarms, notes) + page; navigation and Notes are drawers.
export function DashboardLayout({ children }: DashboardLayoutProps) {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  const isNotesPage = location.pathname === "/notes";
  const { isNotesCollapsed, setIsNotesCollapsed } = useNotesSidebar();
  const breakpoint = useBreakpoint();
  const [isNotesDrawerOpen, setIsNotesDrawerOpen] = useState(false);

  // The drawer belongs to the smaller layouts; it never stays open across a resize or a page change.
  useEffect(() => {
    setIsNotesDrawerOpen(false);
  }, [breakpoint, location.pathname]);

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

  const showNotes = !isNotesPage;
  const openNotesDrawer = () => setIsNotesDrawerOpen(true);

  // When printing, only the page itself shows (e.g. a report), unclipped by the scroll containers.
  return (
    <div
      data-shell={breakpoint}
      // A column (top bar above the page) on phones, a row (navigation beside it) otherwise; by
      // breakpoint, not width alone: a sideways phone is a phone.
      className={`h-dvh bg-background flex ${breakpoint === "phone" ? "flex-col" : "flex-row"} w-full overflow-hidden print:block print:h-auto print:overflow-visible`}
    >
      {breakpoint === "phone" ? (
        <MobileTopBar onOpenNotes={showNotes ? openNotesDrawer : undefined} />
      ) : (
        <AppSidebar />
      )}
      <div className="flex-1 flex min-h-0 min-w-0 overflow-hidden print:block print:overflow-visible">
        <main className="flex-1 min-w-0 overflow-auto print:overflow-visible">
          {children}
        </main>

        {showNotes && breakpoint !== "phone" && (
          <div className="relative border-l border-border flex flex-col justify-center print:hidden">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Toggle notes"
              className="h-12 w-4 rounded-none rounded-l-md border-y border-l border-border -mr-[1px] z-10 bg-background hover:bg-muted"
              onClick={breakpoint === "laptop" ? () => setIsNotesCollapsed(!isNotesCollapsed) : openNotesDrawer}
            >
              {breakpoint === "laptop" && !isNotesCollapsed
                ? <PanelLeftClose className="h-3 w-3 rotate-180" />
                : <PanelLeftOpen className="h-3 w-3 rotate-180" />}
            </Button>
          </div>
        )}

        {showNotes && breakpoint === "laptop" && (
          <div
            className={`border-l border-border transition-all duration-300 ease-in-out flex flex-col print:hidden ${
              isNotesCollapsed ? "w-0 opacity-0 overflow-hidden" : "w-80"
            }`}
          >
            <div className="bg-card border border-border rounded-lg p-4 flex flex-col h-full overflow-hidden m-2">
              <Notes />
            </div>
          </div>
        )}
      </div>

      {showNotes && breakpoint !== "laptop" && (
        <Sheet open={isNotesDrawerOpen} onOpenChange={setIsNotesDrawerOpen}>
          <SheetContent side="right" aria-describedby={undefined} className="flex w-full flex-col p-4 pt-12 sm:max-w-sm">
            <SheetTitle className="sr-only">Notes</SheetTitle>
            <Notes className="min-h-0 flex-1" />
          </SheetContent>
        </Sheet>
      )}
    </div>
  );
}
