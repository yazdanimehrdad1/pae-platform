import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { powerflowApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { ProfileFolder, RunState, SiteConfig } from "@/api/types/powerflow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { powerflowKeys, useProfiles } from "../hooks/usePowerflow";
import { useSiteEdits } from "../hooks/useSiteEdits";
import { downsample, parseCsv } from "../lib/csv";
import { ProfileSelection } from "./profiles/ProfileSelection";

const CHART_POINTS = 400;
const PREVIEW_ROWS = 8;
const LINE_COLOURS = ["hsl(var(--primary))", "#f59e0b", "#10b981", "#0ea5e9"];

function ProfileView({ folder, scenario }: { folder: ProfileFolder; scenario: string }) {
  const csv = useQuery({
    queryKey: powerflowKeys.profileCsv(folder, scenario),
    queryFn: () => powerflowApi.getProfileCsv(folder, scenario),
    retry: false,
  });
  const parsed = useMemo(() => (csv.data ? parseCsv(csv.data) : null), [csv.data]);
  const series = useMemo(
    () => (parsed ? parsed.columns.filter((column) => column !== "timestamp") : []),
    [parsed],
  );
  const chartRows = useMemo(() => {
    if (!parsed) return [];
    const timeIndex = parsed.columns.indexOf("timestamp");
    return downsample(parsed.rows, CHART_POINTS).map((row) => ({
      time: (row[timeIndex] ?? "").replace("T", " ").slice(0, 16),
      ...Object.fromEntries(series.map((column) => [column, Number(row[parsed.columns.indexOf(column)])])),
    }));
  }, [parsed, series]);

  if (csv.isLoading) return <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />;
  if (csv.isError) return <p role="alert" className="text-destructive">{getErrorMessage(csv.error)}</p>;
  if (!parsed) return null;

  return (
    <div className="space-y-4" data-profile-view={`${folder}/${scenario}`}>
      <p className="text-sm text-muted-foreground">
        {parsed.rows.length.toLocaleString()} rows · columns {parsed.columns.join(", ")}
      </p>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartRows}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="time" minTickGap={60} tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            {series.map((column, index) => (
              <Line key={column} type="monotone" dataKey={column} dot={false} stroke={LINE_COLOURS[index % LINE_COLOURS.length]} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            {parsed.columns.map((column) => (
              <TableHead key={column}>{column}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {parsed.rows.slice(0, PREVIEW_ROWS).map((row, index) => (
            <TableRow key={index}>
              {row.map((cell, cellIndex) => (
                <TableCell key={cellIndex}>{cell}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

interface Props {
  siteName: string;
  config: SiteConfig;
  isActive: boolean;
  runState: RunState | undefined;
}

// The profile scenarios (CSV time series): choose which one each load and PV of the selected
// site follows, and preview any of them. A scenario button says which assets use it.
export function ProfilesPanel({ siteName, config, isActive, runState }: Props) {
  const profiles = useProfiles();
  const siteEdits = useSiteEdits(config);
  const [selected, setSelected] = useState<{ folder: ProfileFolder; scenario: string } | null>(null);

  if (profiles.isLoading) return <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />;
  if (profiles.isError) return <p role="alert" className="text-destructive">{getErrorMessage(profiles.error)}</p>;

  const groups: { folder: ProfileFolder; title: string; scenarios: string[] }[] = [
    { folder: "load", title: "Load scenarios", scenarios: profiles.data?.load ?? [] },
    { folder: "pv", title: "PV scenarios", scenarios: profiles.data?.pv ?? [] },
  ];
  // The assets of the stored site that follow each scenario.
  const assets: Record<ProfileFolder, { id: string; label: string; scenario: string }[]> = {
    load: (config.loads ?? []).map((load) => ({ id: load.id, label: load.name ?? load.id, scenario: load.profile.scenario })),
    pv: (config.pv ?? []).map((pv) => ({ id: pv.id, label: pv.name ?? pv.id, scenario: pv.availability.scenario })),
  };
  const assignScenario = (folder: ProfileFolder, id: string, scenario: string) =>
    siteEdits.setEdits((current) => {
      const key = folder === "load" ? "loadProfiles" : "pvProfiles";
      return { ...current, [key]: { ...current[key], [id]: { ...current[key][id], scenario } } };
    });

  return (
    <div className="space-y-4">
      <ProfileSelection
        siteName={siteName}
        config={config}
        isActive={isActive}
        runState={runState}
        loadScenarios={profiles.data?.load ?? []}
        pvScenarios={profiles.data?.pv ?? []}
        siteEdits={siteEdits}
      />
      <Card>
        <CardHeader>
          <CardTitle>Profiles</CardTitle>
          <CardDescription>The time series the loads and PV can follow. Click one to preview it.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {groups.map((group) => (
            <div key={group.folder} className="space-y-2">
              <p className="text-sm font-semibold text-foreground">{group.title}</p>
              <div className="flex flex-wrap gap-2">
                {group.scenarios.map((scenario) => {
                  const previewed = selected?.folder === group.folder && selected.scenario === scenario;
                  const usedBy = assets[group.folder].filter((asset) => asset.scenario === scenario);
                  return (
                    <Button
                      key={scenario}
                      size="sm"
                      variant={previewed ? "default" : "outline"}
                      className="gap-2"
                      data-profile-scenario={`${group.folder}/${scenario}`}
                      onClick={() => setSelected({ folder: group.folder, scenario })}
                    >
                      {scenario}
                      {usedBy.length > 0 && (
                        <Badge variant="secondary" className="font-normal">
                          in use: {usedBy.map((asset) => asset.id).join(", ")}
                        </Badge>
                      )}
                    </Button>
                  );
                })}
              </div>
            </div>
          ))}
          {selected && (
            <div className="flex flex-wrap gap-2">
              {assets[selected.folder].map((asset) => (
                <Button
                  key={asset.id}
                  size="sm"
                  variant="secondary"
                  onClick={() => assignScenario(selected.folder, asset.id, selected.scenario)}
                >
                  Use for {asset.label}
                </Button>
              ))}
            </div>
          )}
          {selected && <ProfileView folder={selected.folder} scenario={selected.scenario} />}
        </CardContent>
      </Card>
    </div>
  );
}
