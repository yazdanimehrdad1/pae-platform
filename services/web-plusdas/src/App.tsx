import { lazy, Suspense } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/shared/contexts/auth";
import { DashboardLayout } from "@/shared/components/layout/DashboardLayout";
import { ThemeProvider } from "@/shared/components/theme-provider";
import { NotesSidebarProvider } from "@/shared/contexts/NotesSidebarContext";

const Login = lazy(() => import("@/features/auth/LoginPage"));
const Historian = lazy(() => import("@/features/historian/HistorianPage"));
const LiveData = lazy(() => import("@/features/live-data/LiveDataPage"));
const Health = lazy(() => import("@/features/health/HealthPage"));
const Sites = lazy(() => import("@/features/sites/SitesPage"));
const ManageSites = lazy(() => import("@/features/sites/ManageSitesPage"));
const SiteDevices = lazy(() => import("@/features/sites/SiteDevicesPage"));
const ManageDevices = lazy(() => import("@/features/sites/ManageDevicesPage"));
const DeviceDetails = lazy(() => import("@/features/devices/DeviceDetailsPage"));
const Narrative = lazy(() => import("@/features/narrative/NarrativePage"));
const Reports = lazy(() => import("@/features/reports/ReportsPage"));
const SLD = lazy(() => import("@/features/sld/SLDPage"));
const TaskBuilder = lazy(() => import("@/features/task-builder/TaskBuilderPage"));
const NotesPage = lazy(() => import("@/features/notes/NotesPage"));
const Settings = lazy(() => import("@/features/settings/SettingsPage"));
const NotFound = lazy(() => import("./pages/NotFound"));

const queryClient = new QueryClient();

const PageLoader = () => (
  <div className="flex items-center justify-center h-screen">
    <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
  </div>
);

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
        <AuthProvider>
          <NotesSidebarProvider>
            <Toaster />
            <Sonner />
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/" element={<Navigate to="/sites" replace />} />
                <Route path="/health" element={<DashboardLayout><Health /></DashboardLayout>} />
                <Route path="/historian" element={<DashboardLayout><Historian /></DashboardLayout>} />
                <Route path="/live-data" element={<DashboardLayout><LiveData /></DashboardLayout>} />
                <Route path="/sites" element={<DashboardLayout><Sites /></DashboardLayout>} />
                <Route path="/sites/manage" element={<DashboardLayout><ManageSites /></DashboardLayout>} />
                <Route path="/site-devices" element={<DashboardLayout><SiteDevices /></DashboardLayout>} />
                <Route path="/site-devices/manage" element={<DashboardLayout><ManageDevices /></DashboardLayout>} />
                <Route path="/devices/:deviceId" element={<DashboardLayout><DeviceDetails /></DashboardLayout>} />
                <Route path="/narrative" element={<DashboardLayout><Narrative /></DashboardLayout>} />
                <Route path="/reports" element={<DashboardLayout><Reports /></DashboardLayout>} />
                <Route path="/sld" element={<DashboardLayout><SLD /></DashboardLayout>} />
                <Route path="/task-builder" element={<DashboardLayout><TaskBuilder /></DashboardLayout>} />
                <Route path="/users" element={<DashboardLayout><div className="p-6"><h1 className="text-3xl font-bold">User Management</h1><p className="text-muted-foreground mt-2">User administration coming soon</p></div></DashboardLayout>} />
                <Route path="/settings" element={<DashboardLayout><Settings /></DashboardLayout>} />
                <Route path="/notes" element={<DashboardLayout><NotesPage /></DashboardLayout>} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </NotesSidebarProvider>
        </AuthProvider>
      </ThemeProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
