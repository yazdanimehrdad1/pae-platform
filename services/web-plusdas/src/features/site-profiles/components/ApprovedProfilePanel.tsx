import { useMemo, useState } from "react";
import type { ProfilePoint, ProfileVersion } from "@/api/types/siteProfiles";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime, labelsText, localPointName } from "../lib/changes";
import { SiteFunctionsSection } from "./SiteFunctionsSection";

// What the AI knows of the site's facts right now: the approved profile version. (Engineer
// knowledge, the meaning, limits and fault guides of each point, comes in a later step.)

function matches(point: ProfilePoint, filter: string): boolean {
  if (!filter) return true;
  const needle = filter.toLowerCase();
  return [point.name, point.description ?? "", point.unit ?? ""].some(text => text.toLowerCase().includes(needle));
}

export function ApprovedProfilePanel({ profile, timeZone }: { profile: ProfileVersion | undefined; timeZone: string }) {
  const [filter, setFilter] = useState("");
  const pointsByDevice = useMemo(() => {
    const grouped = new Map<number, ProfilePoint[]>();
    for (const point of profile?.catalog.points ?? []) {
      if (!matches(point, filter.trim())) continue;
      grouped.set(point.device_id, [...(grouped.get(point.device_id) ?? []), point]);
    }
    return grouped;
  }, [profile, filter]);

  if (!profile) {
    return <p className="text-muted-foreground">Not onboarded yet: the AI doesn't see this site. Approve its pending changes first.</p>;
  }
  const { site, devices, points, topology, functions = [] } = profile.catalog;

  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <Fact label="Version" value={`v${profile.version} · ${formatDateTime(profile.approved_at, timeZone)}`} />
        <Fact label="Approved by" value={profile.approved_by} />
        <Fact label="Time zone" value={site.timezone ?? "UTC"} />
        <Fact label="Capacity" value={site.capacity_kw != null ? `${site.capacity_kw.toLocaleString()} kW` : "—"} />
        <Fact label="Devices" value={String(devices.length)} />
        <Fact label="Points" value={String(points.length)} />
        <Fact label="Topology" value={`${topology?.nodes?.length ?? 0} nodes, ${topology?.connections?.length ?? 0} connections`} />
        <Fact label="Site functions" value={String(functions.length)} />
      </dl>

      <Input
        placeholder="Filter points by name, description or unit"
        value={filter}
        onChange={event => setFilter(event.target.value)}
        className="w-full sm:w-96"
        aria-label="Filter points"
      />

      <Accordion type="multiple" className="rounded-md border">
        {devices.map(device => {
          const devicePoints = pointsByDevice.get(device.device_id) ?? [];
          if (filter.trim() && devicePoints.length === 0) return null;
          return (
            <AccordionItem key={device.device_id} value={String(device.device_id)}>
              <AccordionTrigger className="px-3 hover:no-underline">
                <span className="flex flex-wrap items-baseline gap-x-2 text-left">
                  <span className="font-medium">{device.name}</span>
                  <span className="text-sm text-muted-foreground">
                    {device.type}{device.vendor ? ` · ${device.vendor}` : ""}{device.model ? ` ${device.model}` : ""} · {devicePoints.length} points
                  </span>
                </span>
              </AccordionTrigger>
              <AccordionContent className="px-3">
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Point</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead>Unit</TableHead>
                        <TableHead>Class</TableHead>
                        <TableHead>Severity</TableHead>
                        <TableHead>States / bits</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {devicePoints.map(point => (
                        <TableRow key={point.name}>
                          <TableCell className="font-mono text-xs whitespace-nowrap">{localPointName(point)}</TableCell>
                          <TableCell>{point.description ?? <span className="text-muted-foreground">—</span>}</TableCell>
                          <TableCell>{point.unit ?? ""}</TableCell>
                          <TableCell>{point.point_class ?? ""}</TableCell>
                          <TableCell>{point.severity ?? ""}</TableCell>
                          <TableCell className="text-xs text-muted-foreground max-w-md">{labelsText(point)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </AccordionContent>
            </AccordionItem>
          );
        })}
      </Accordion>

      <SiteFunctionsSection siteId={profile.site_id} functions={functions} devices={devices} timeZone={timeZone} />
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium break-words">{value}</dd>
    </div>
  );
}
