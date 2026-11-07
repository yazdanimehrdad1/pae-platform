import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { siteProfilesApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/shared/contexts/auth";
import { ApprovedProfilePanel } from "./components/ApprovedProfilePanel";
import { PendingChangesPanel } from "./components/PendingChangesPanel";
import { SITE_PROFILES_QUERY_KEY, formatDateTime, statusOf } from "./lib/changes";

// One site's AI profile: the backend-ot changes to review and approve, what the AI knows now,
// and every approved version.

export default function SiteProfileDetailPage() {
  const { user } = useAuth();
  const siteId = Number(useParams().siteId);
  const isAdmin = user?.role === "admin";
  const profile = useQuery({
    queryKey: ["site-profiles", siteId, "profile"],
    queryFn: () => siteProfilesApi.get(siteId),
    enabled: isAdmin && Number.isFinite(siteId),
    retry: false,
  });
  const statuses = useQuery({ queryKey: SITE_PROFILES_QUERY_KEY, queryFn: siteProfilesApi.list, enabled: isAdmin });

  if (!isAdmin) {
    return (
      <div className="p-4 md:p-6">
        <h1 className="text-2xl md:text-3xl font-bold">AI Site Profile</h1>
        <p className="text-muted-foreground mt-2">Only administrators manage what the AI knows about each site.</p>
      </div>
    );
  }

  const notOnboarded = profile.isError && statusOf(profile.error) === 404;
  const status = statuses.data?.find(entry => entry.site_id === siteId);
  const name = profile.data?.catalog.site.name ?? status?.name ?? `Site ${siteId}`;
  const onboarded = profile.data !== undefined;

  return (
    <div className="p-4 md:p-6 space-y-4">
      <Link to="/site-profiles" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="w-4 h-4 mr-1" />AI Site Profiles
      </Link>
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-foreground">{name}</h1>
        <p className="text-muted-foreground mt-1">
          {onboarded ? `The AI uses profile version ${profile.data.version}.` : "Not onboarded: the AI doesn't see this site yet."}
        </p>
      </div>
      {profile.isError && !notOnboarded && (
        <p className="text-destructive">Could not load the profile: {getErrorMessage(profile.error)}</p>
      )}

      <Tabs defaultValue="changes">
        <TabsList className="flex-wrap h-auto">
          <TabsTrigger value="changes">Pending changes{status?.pending_changes ? ` (${status.pending_changes})` : ""}</TabsTrigger>
          <TabsTrigger value="profile">What the AI knows</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>
        <TabsContent value="changes" className="pt-2">
          {profile.isLoading ? <p className="text-muted-foreground">Loading...</p> : <PendingChangesPanel siteId={siteId} onboarded={onboarded} />}
        </TabsContent>
        <TabsContent value="profile" className="pt-2">
          <ApprovedProfilePanel profile={profile.data} />
        </TabsContent>
        <TabsContent value="history" className="pt-2">
          <VersionHistory siteId={siteId} enabled={onboarded} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function VersionHistory({ siteId, enabled }: { siteId: number; enabled: boolean }) {
  const { data: versions = [], isLoading, isError, error } = useQuery({
    queryKey: ["site-profiles", siteId, "versions"],
    queryFn: () => siteProfilesApi.versions(siteId),
    enabled,
    retry: false,
  });
  if (!enabled) return <p className="text-muted-foreground">No approved version yet.</p>;
  if (isLoading) return <p className="text-muted-foreground">Loading history...</p>;
  if (isError) return <p className="text-destructive">Could not load the history: {getErrorMessage(error)}</p>;
  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Version</TableHead>
            <TableHead>Approved</TableHead>
            <TableHead>By</TableHead>
            <TableHead>Changes</TableHead>
            <TableHead>Devices</TableHead>
            <TableHead>Points</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {versions.map(version => (
            <TableRow key={version.version}>
              <TableCell className="font-medium">v{version.version}</TableCell>
              <TableCell className="whitespace-nowrap">{formatDateTime(version.approved_at)}</TableCell>
              <TableCell>{version.approved_by}</TableCell>
              <TableCell>{version.change_ids.length}</TableCell>
              <TableCell>{version.devices}</TableCell>
              <TableCell>{version.points}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
