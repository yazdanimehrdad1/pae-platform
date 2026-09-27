import { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/shared/contexts/auth";
import { NotesSidebarProvider } from "@/shared/contexts/NotesSidebarContext";
import { ThemeProvider } from "@/shared/components/theme-provider";

const queryClient = new QueryClient();

// App-wide providers and toasters, outermost first.
export const AppProviders = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
        <AuthProvider>
          <NotesSidebarProvider>
            <Toaster />
            <Sonner />
            {children}
          </NotesSidebarProvider>
        </AuthProvider>
      </ThemeProvider>
    </TooltipProvider>
  </QueryClientProvider>
);
