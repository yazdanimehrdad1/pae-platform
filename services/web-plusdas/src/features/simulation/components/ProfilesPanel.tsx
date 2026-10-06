import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { powerflowApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { ProfileFolder } from "@/api/types/powerflow";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { powerflowKeys, useProfiles } from "../hooks/usePowerflow";
import { downsample, parseCsv } from "../lib/csv";

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

// The profile scenarios (CSV time series) the sites can follow. View only.
export function ProfilesPanel() {
  const profiles = useProfiles();
  const [selected, setSelected] = useState<{ folder: ProfileFolder; scenario: string } | null>(null);

  if (profiles.isLoading) return <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />;
  if (profiles.isError) return <p role="alert" className="text-destructive">{getErrorMessage(profiles.error)}</p>;

  const groups: { folder: ProfileFolder; title: string; scenarios: string[] }[] = [
    { folder: "load", title: "Load scenarios", scenarios: profiles.data?.load ?? [] },
    { folder: "pv", title: "PV scenarios", scenarios: profiles.data?.pv ?? [] },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profiles</CardTitle>
        <CardDescription>Time series the loads and PV follow. Pick a scenario for a site under Site settings.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {groups.map((group) => (
          <div key={group.folder} className="space-y-2">
            <p className="text-sm font-semibold text-foreground">{group.title}</p>
            <div className="flex flex-wrap gap-2">
              {group.scenarios.map((scenario) => {
                const active = selected?.folder === group.folder && selected.scenario === scenario;
                return (
                  <Button key={scenario} size="sm" variant={active ? "default" : "outline"} onClick={() => setSelected({ folder: group.folder, scenario })}>
                    {scenario}
                  </Button>
                );
              })}
            </div>
          </div>
        ))}
        {selected && <ProfileView folder={selected.folder} scenario={selected.scenario} />}
      </CardContent>
    </Card>
  );
}
