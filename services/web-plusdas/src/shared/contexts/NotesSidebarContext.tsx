import { createContext, useContext, useState, useEffect, ReactNode } from "react";

interface NotesSidebarContextType {
  isNotesCollapsed: boolean;
  setIsNotesCollapsed: (collapsed: boolean) => void;
}

const NotesSidebarContext = createContext<NotesSidebarContextType | undefined>(undefined);

const NOTES_PANEL_STORAGE_KEY = "notes_panel_collapsed";

export function NotesSidebarProvider({ children }: { children: ReactNode }) {
  const [isNotesCollapsed, setIsNotesCollapsed] = useState(() => {
    const saved = localStorage.getItem(NOTES_PANEL_STORAGE_KEY);
    return saved ? JSON.parse(saved) : false;
  });

  useEffect(() => {
    localStorage.setItem(NOTES_PANEL_STORAGE_KEY, JSON.stringify(isNotesCollapsed));
  }, [isNotesCollapsed]);

  return (
    <NotesSidebarContext.Provider value={{ isNotesCollapsed, setIsNotesCollapsed }}>
      {children}
    </NotesSidebarContext.Provider>
  );
}

export function useNotesSidebar() {
  const context = useContext(NotesSidebarContext);
  if (context === undefined) {
    throw new Error("useNotesSidebar must be used within a NotesSidebarProvider");
  }
  return context;
}
