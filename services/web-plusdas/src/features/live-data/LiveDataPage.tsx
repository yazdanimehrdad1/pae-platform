import { useState, useEffect, useRef, Fragment } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Network, Radio, Zap, PanelLeftClose, PanelLeftOpen, RotateCw, Trash2 } from "lucide-react";
import { sitesApi } from "@/api";
import { DeviceAssetTree } from "@/shared/components/DeviceAssetTree";
import { useNotesSidebar } from "@/shared/contexts/NotesSidebarContext";
import { useModbusSessions } from "./hooks/useModbusSessions";
import { useModbusConfigSlots } from "./hooks/useModbusConfigSlots";
import { ModbusStreamForm } from "./modbus/ModbusStreamForm";
import { ModbusSessionCard } from "./modbus/ModbusSessionCard";
import { ModbusSessionsOverview } from "./modbus/ModbusSessionsOverview";

const MAX_SIGNALS = 10;

export default function LiveData() {
  const { isNotesCollapsed, setIsNotesCollapsed } = useNotesSidebar();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [selectedSiteId, setSelectedSiteId] = useState<string>('');
  const [selectedPoints, setSelectedPoints] = useState<string[]>([]);
  const [pointLabels, setPointLabels] = useState<Record<string, string>>({});
  const previousSidebarStateRef = useRef<boolean | null>(null);
  const previousNotesStateRef = useRef<boolean | null>(null);

  const { data: sites = [] } = useQuery({
    queryKey: ['sites'],
    queryFn: sitesApi.getAll,
  });

  useEffect(() => {
    if (!selectedSiteId && sites.length > 0) setSelectedSiteId(sites[0].id);
  }, [sites, selectedSiteId]);

  useEffect(() => {
    setSelectedPoints([]);
    setPointLabels({});
  }, [selectedSiteId]);

  useEffect(() => {
    if (!isNotesCollapsed) {
      if (previousSidebarStateRef.current === null) {
        previousSidebarStateRef.current = isSidebarOpen;
      }
      setIsSidebarOpen(false);
    } else {
      if (previousSidebarStateRef.current !== null) {
        setIsSidebarOpen(previousSidebarStateRef.current);
        previousSidebarStateRef.current = null;
      }
    }
  }, [isNotesCollapsed, isSidebarOpen]);

  const handleAssetTreeToggle = () => {
    if (!isSidebarOpen && !isNotesCollapsed) {
      if (previousNotesStateRef.current === null) {
        previousNotesStateRef.current = isNotesCollapsed;
      }
      setIsNotesCollapsed(true);
      setIsSidebarOpen(true);
    } else if (isSidebarOpen && previousNotesStateRef.current !== null) {
      setIsNotesCollapsed(previousNotesStateRef.current);
      previousNotesStateRef.current = null;
      setIsSidebarOpen(false);
    } else {
      setIsSidebarOpen(!isSidebarOpen);
    }
  };

  const handleSelectPoints = (points: string[], labels: Record<string, string>) => {
    setPointLabels(prev => ({ ...prev, ...labels }));
    setSelectedPoints(points);
  };

  const handleResolveLabels = (labels: Record<string, string>) => {
    setPointLabels(prev => ({ ...prev, ...labels }));
  };

  const selectedSite = sites.find(site => site.id === selectedSiteId);
  const {
    sessions, refresh, isLoading,
    relaunchSlot, resumeSession, stopSession, deleteSession, deleteAllSessions,
  } = useModbusSessions();
  const { configsBySlot, nextFreeSlot, saveConfig, removeConfig, clearAllConfigs } = useModbusConfigSlots();
  const configSlots = [...new Set([...Object.keys(configsBySlot).map(Number), ...(nextFreeSlot !== null ? [nextFreeSlot] : [])])].sort((a, b) => a - b);
  const sessionBySlot = new Map(sessions.map(s => [s.slot, s]));
  const aliasBySlot = Object.fromEntries(Object.entries(configsBySlot).map(([slot, entry]) => [slot, entry.alias]));
  const [modbusSubTab, setModbusSubTab] = useState<string>('config-1');
  const [activeTab, setActiveTab] = useState<'points' | 'modbus'>('points');
  const showAssetTreeSidebar = isSidebarOpen && activeTab !== 'modbus';
  const [isDeleteAllDialogOpen, setIsDeleteAllDialogOpen] = useState(false);

  useEffect(() => {
    if (!modbusSubTab.startsWith('config-') && modbusSubTab !== 'all-sessions' && !sessions.some(s => s.sessionId === modbusSubTab)) {
      setModbusSubTab('config-1');
    }
  }, [sessions, modbusSubTab]);

  return (
    <div className="h-screen flex flex-col">
      <div className="border-b border-border p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Live Data</h1>
            <p className="text-muted-foreground mt-1">Real-time monitoring of selected signals via WebSocket</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="bg-warning/10 text-warning border-warning">
              <Radio className="w-3 h-3 mr-1" />
              Coming Soon
            </Badge>
            <Badge variant="outline" className="gap-2">
              <Zap className="w-3 h-3" />
              {selectedPoints.length}/{MAX_SIGNALS} Signals
            </Badge>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div
          className={`border-r border-border transition-all duration-300 ease-in-out flex flex-col overflow-hidden ${showAssetTreeSidebar ? 'w-80' : 'w-0 opacity-0'}`}
        >
          <div className="flex-1 overflow-hidden min-w-[20rem]">
            <Card className="h-full rounded-none border-0 flex flex-col">
              <CardHeader className="pb-4 shrink-0 space-y-3">
                <CardTitle className="flex items-center text-lg">
                  <Network className="w-5 h-5 mr-2" />
                  Asset Tree
                </CardTitle>
                <CardDescription>
                  Select up to {MAX_SIGNALS} signals to monitor
                </CardDescription>
                <div className="space-y-1">
                  <Label htmlFor="live-data-site">Site</Label>
                  <Select value={selectedSiteId} onValueChange={setSelectedSiteId}>
                    <SelectTrigger id="live-data-site"><SelectValue placeholder="Select a site" /></SelectTrigger>
                    <SelectContent>
                      {sites.map(site => <SelectItem key={site.id} value={site.id}>{site.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent className="p-4 flex-1 overflow-auto">
                <DeviceAssetTree
                  siteId={selectedSiteId || null}
                  siteName={selectedSite?.name ?? 'Site'}
                  selectedPoints={selectedPoints}
                  onSelect={handleSelectPoints}
                  onResolveLabels={handleResolveLabels}
                  maxPoints={MAX_SIGNALS}
                />
              </CardContent>
            </Card>
          </div>
        </div>

        {activeTab !== 'modbus' && (
          <div className="relative border-r border-border flex flex-col justify-center">
            <Button
              variant="ghost"
              size="icon"
              className="h-12 w-4 rounded-none rounded-r-md border-y border-r border-border -ml-[1px] z-10 bg-background hover:bg-muted"
              onClick={handleAssetTreeToggle}
            >
              {isSidebarOpen ? <PanelLeftClose className="h-3 w-3" /> : <PanelLeftOpen className="h-3 w-3" />}
            </Button>
          </div>
        )}

        <div className="flex-1 flex flex-col min-h-0">
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'points' | 'modbus')} className="flex-1 flex flex-col min-h-0">
            <div className="border-b border-border px-6 pt-4">
              <TabsList>
                <TabsTrigger value="points">Point Monitoring</TabsTrigger>
                <TabsTrigger value="modbus">Modbus Debug</TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="points" className="flex-1 flex-col min-h-0 mt-0 data-[state=active]:flex">
              {selectedPoints.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-6">
                  <div className="w-16 h-16 bg-muted/50 rounded-full flex items-center justify-center mb-4">
                    <Radio className="w-8 h-8 opacity-50" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">No Signals Selected</h3>
                  <p className="max-w-sm text-center">
                    Select signals from the Asset Tree on the left to begin live monitoring
                  </p>
                </div>
              ) : (
                <div className="flex-1 p-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Radio className="w-5 h-5" />
                        Live Data Monitoring
                      </CardTitle>
                      <CardDescription>
                        Real-time data visualization will appear here once WebSocket connection is implemented
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="bg-muted/30 rounded-lg p-8 border border-dashed border-border text-center">
                        <Radio className="w-16 h-16 mx-auto mb-4 text-muted-foreground/50" />
                        <h3 className="text-xl font-semibold text-foreground mb-2">
                          Feature Coming Soon
                        </h3>
                        <p className="text-sm text-muted-foreground mb-4 max-w-md mx-auto">
                          Live data monitoring with WebSocket connection is currently under development.
                          You can select up to {MAX_SIGNALS} signals from the asset tree, and they will be displayed here once the feature is available.
                        </p>
                        <div className="mt-6 space-y-2">
                          <p className="text-sm font-semibold text-foreground">Selected Signals ({selectedPoints.length}):</p>
                          <div className="flex flex-wrap gap-2 justify-center">
                            {selectedPoints.map((pointId) => (
                              <Badge key={pointId} variant="outline" className="text-xs">
                                {pointLabels[pointId] ?? pointId}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
            </TabsContent>

            <TabsContent value="modbus" className="flex-1 flex-col min-h-0 mt-0 data-[state=active]:flex">
              <Tabs value={modbusSubTab} onValueChange={setModbusSubTab} className="flex-1 flex flex-col min-h-0">
                <div className="border-b border-border px-6 pt-3 flex items-center justify-between gap-3">
                  <TabsList className="h-auto gap-2 bg-transparent p-0">
                    <TabsTrigger value="all-sessions">All Sessions</TabsTrigger>
                    {configSlots.map((slot) => {
                      const alias = aliasBySlot[slot];
                      const suffix = alias ? ` · ${alias}` : '';
                      return (
                        <div key={slot} className="flex items-center gap-1 rounded-lg border-2 border-primary/40 bg-card p-1 shadow-sm">
                          <TabsTrigger value={`config-${slot}`}>Config {slot}{suffix}</TabsTrigger>
                          {sessionBySlot.has(slot) && (
                            <TabsTrigger value={sessionBySlot.get(slot)!.sessionId}>Session {slot}{suffix}</TabsTrigger>
                          )}
                        </div>
                      );
                    })}
                  </TabsList>
                  <div className="flex items-center gap-2 pb-2">
                    <Button variant="outline" size="sm" className="gap-1" onClick={() => refresh()} disabled={isLoading}>
                      <RotateCw className="w-3 h-3" />Refresh
                    </Button>
                    <Button variant="outline" size="sm" className="gap-1 text-destructive hover:text-destructive"
                      onClick={() => setIsDeleteAllDialogOpen(true)} disabled={sessions.length === 0 && Object.keys(configsBySlot).length === 0}>
                      <Trash2 className="w-3 h-3" />Delete All
                    </Button>
                  </div>
                </div>

                <TabsContent value="all-sessions" className="flex-1 overflow-y-auto p-6 mt-0">
                  <ModbusSessionsOverview sessions={sessions} aliasBySlot={aliasBySlot} onSelect={setModbusSubTab} />
                </TabsContent>

                {configSlots.map((slot) => {
                  const session = sessionBySlot.get(slot);
                  return (
                    <Fragment key={slot}>
                      <TabsContent value={`config-${slot}`} className="flex-1 overflow-y-auto p-6 mt-0">
                        <ModbusStreamForm
                          siteId={selectedSiteId || null}
                          initialValues={configsBySlot[slot]?.request}
                          initialAlias={configsBySlot[slot]?.alias}
                          onSubmit={async (request, alias) => {
                            saveConfig(slot, request, alias);
                            const sessionId = await relaunchSlot(slot, request);
                            setModbusSubTab(sessionId);
                          }}
                        />
                      </TabsContent>
                      {session && (
                        <TabsContent value={session.sessionId} className="flex-1 overflow-y-auto p-6 mt-0">
                          <ModbusSessionCard
                            session={session}
                            alias={aliasBySlot[slot]}
                            onResume={() => resumeSession(session.sessionId)}
                            onStop={() => stopSession(session.sessionId)}
                            onDelete={() => { deleteSession(session.sessionId); removeConfig(slot); setModbusSubTab('config-1'); }}
                          />
                        </TabsContent>
                      )}
                    </Fragment>
                  );
                })}
              </Tabs>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      <AlertDialog open={isDeleteAllDialogOpen} onOpenChange={setIsDeleteAllDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete All Sessions</AlertDialogTitle>
            <AlertDialogDescription>
              This will stop and remove all Modbus sessions and saved configurations ({sessions.length} sessions, {Object.keys(configsBySlot).length} saved configs). This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => { deleteAllSessions(); clearAllConfigs(); setModbusSubTab('config-1'); setIsDeleteAllDialogOpen(false); }}
            >
              Delete All
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
