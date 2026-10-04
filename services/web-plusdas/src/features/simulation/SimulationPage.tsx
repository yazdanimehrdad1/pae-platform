import { useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { getErrorMessage } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AssetsPanel } from "./components/AssetsPanel";
import { ModbusPanel } from "./components/ModbusPanel";
import { ProfilesPanel } from "./components/ProfilesPanel";
import { RunControls, RunStateBadge } from "./components/RunControls";
import { ScenariosPanel } from "./components/ScenariosPanel";
import { SimulationSld } from "./components/SimulationSld";
import { SiteSettingsForm } from "./components/SiteSettingsForm";
import { SitesPanel } from "./components/SitesPanel";
import { useActivateSite, useSimStatus, useSite, useSites } from "./hooks/usePowerflow";

// The powerflow simulator: pick one of the stored sites, run it, send setpoints, and look at its
// profiles and Modbus layout. Sites can't be created here, only selected (and a few selection
// fields edited). Talks to powerflow through the same-origin /powerflow-api prefix.
const SimulationPage = () => {
  const sites = useSites();
  const status = useSimStatus();
  const [chosen, setChosen] = useState<string | null>(null);
  const selected = chosen ?? sites.data?.active ?? null;
  const site = useSite(selected ?? undefined);
  const activate = useActivateSite();
  const runState = status.data?.state;
  const active = sites.data?.active;
  const selectedIsActive = selected !== null && selected === active;

  if (sites.isLoading) {
    return (
      <div className="p-6 flex items-center gap-2 text-muted-foreground">
        <Loader2 className="w-5 h-5 animate-spin" /> Connecting to the simulator...
      </div>
    );
  }
  if (sites.isError || !sites.data) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="p-6 text-center space-y-4">
            <AlertTriangle className="w-8 h-8 mx-auto text-destructive" />
            <p className="text-destructive">{getErrorMessage(sites.error, "The powerflow simulator is not reachable")}</p>
            <Button onClick={() => sites.refetch()}>Retry</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Simulation</h1>
          <p className="text-muted-foreground mt-1">The powerflow microgrid simulator: choose a site, run it and send setpoints</p>
        </div>
        <div className="flex items-center gap-3">
          {runState && <RunStateBadge state={runState} />}
          <Select value={selected ?? undefined} onValueChange={setChosen}>
            <SelectTrigger className="w-64" aria-label="Site">
              <SelectValue placeholder="Select site" />
            </SelectTrigger>
            <SelectContent>
              {sites.data.sites.map((name) => (
                <SelectItem key={name} value={name}>
                  {name}
                  {name === active ? " (active)" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            disabled={!selected || selectedIsActive || activate.isPending}
            onClick={() => selected && activate.mutate({ name: selected, state: runState })}
          >
            {runState && runState !== "stopped" ? "Stop & activate" : "Activate"}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="settings">Site settings</TabsTrigger>
          <TabsTrigger value="assets">Assets & setpoints</TabsTrigger>
          <TabsTrigger value="profiles">Profiles</TabsTrigger>
          <TabsTrigger value="modbus">Modbus</TabsTrigger>
          <TabsTrigger value="sites">Sites & defaults</TabsTrigger>
          <TabsTrigger value="scenarios">Scenarios</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          {status.data ? (
            <RunControls status={status.data} />
          ) : status.isError ? (
            <p role="alert" className="text-destructive">{getErrorMessage(status.error)}</p>
          ) : null}
          <Card>
            <CardHeader>
              <CardTitle>{site.data?.site?.name ?? selected}</CardTitle>
              <CardDescription>
                Single line diagram of {selected}
                {selectedIsActive ? " (the active site)" : ", not active: Activate it to simulate it"}.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {site.isLoading && <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />}
              {site.isError && <p role="alert" className="text-destructive">{getErrorMessage(site.error)}</p>}
              {site.data && <SimulationSld config={site.data} />}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="settings">
          {site.data && selected && (
            <SiteSettingsForm
              key={`${selected}-${site.dataUpdatedAt}`}
              siteName={selected}
              config={site.data}
              isActive={selectedIsActive}
              runState={runState}
            />
          )}
        </TabsContent>

        <TabsContent value="assets">
          <AssetsPanel selectedIsActive={selectedIsActive} />
        </TabsContent>

        <TabsContent value="profiles">
          <ProfilesPanel />
        </TabsContent>

        <TabsContent value="modbus">{selected && <ModbusPanel siteName={selected} />}</TabsContent>

        <TabsContent value="sites">
          {selected && <SitesPanel sites={sites.data} selected={selected} runState={runState} onSelect={setChosen} />}
        </TabsContent>

        <TabsContent value="scenarios">
          <ScenariosPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default SimulationPage;
