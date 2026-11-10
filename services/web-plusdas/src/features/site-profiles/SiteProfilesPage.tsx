import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { BookOpen, ChevronRight, RefreshCw } from "lucide-react";
import { siteProfilesApi, sitesApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { SiteProfileStatus } from "@/api/types/siteProfiles";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/shared/contexts/auth";
import { toast } from "@/shared/hooks/use-toast";
import { BROWSER_TIME_ZONE, useDisplayTimeZone } from "@/shared/hooks/useDisplayTimeZone";
import { SITE_PROFILES_QUERY_KEY, formatDateTime } from "./lib/changes";

// Every site intelli-gateway has read from backend-ot: whether the AI may use it (onboarded, the
// approved profile version) and how many backend-ot changes wait for an admin's approval.



export default function SiteProfilesPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const isAdmin = user?.role === "admin";
  const { data: statuses = [], isLoading, isError, error } = useQuery({
    queryKey: SITE_PROFILES_QUERY_KEY,
    queryFn: siteProfilesApi.list,
    enabled: isAdmin,
  });
  // Each row's times in that site's zone (backend-ot's site record), or the user's own zone if
  // they chose "My time" (the same preference as every page).
  const { display } = useDisplayTimeZone(null);
  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: sitesApi.getAll, enabled: isAdmin });
  const timeZoneOf = (siteId: number): string =>
    display === "browser" ? BROWSER_TIME_ZONE : sites.find(site => site.id === String(siteId))?.timezone ?? BROWSER_TIME_ZONE;
  const syncAll = useMutation({
    mutationFn: siteProfilesApi.syncAll,
    onSuccess: (fresh) => {
      queryClient.setQueryData(SITE_PROFILES_QUERY_KEY, fresh);
      toast({ title: "Read backend-ot", description: `${fresh.length} site(s) checked. Nothing changes for the AI until you approve.` });
    },
    onError: (syncError) => toast({ title: "Could not read backend-ot", description: getErrorMessage(syncError), variant: "destructive" }),
  });

  if (!isAdmin) {
    return (
      <div className="p-4 md:p-6">
        <h1 className="text-2xl md:text-3xl font-bold">AI Site Profiles</h1>
        <p className="text-muted-foreground mt-2">Only administrators manage what the AI knows about each site.</p>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-foreground">AI Site Profiles</h1>
          <p className="text-muted-foreground mt-1 max-w-3xl">
            The AI assistant sees a site only after you approve its profile: the site, its devices, points and topology
            as read from backend-ot. Later changes in backend-ot wait here until you approve them.
          </p>
        </div>
        <Button variant="outline" onClick={() => syncAll.mutate()} disabled={syncAll.isPending}>
          <RefreshCw className={`w-4 h-4 mr-2 ${syncAll.isPending ? "animate-spin" : ""}`} />
          Read backend-ot now
        </Button>
      </div>

      {isLoading && <p className="text-muted-foreground">Loading site profiles...</p>}
      {isError && <p className="text-destructive">Could not load the site profiles: {getErrorMessage(error)}</p>}
      {!isLoading && !isError && statuses.length === 0 && (
        <p className="text-muted-foreground">No site read from backend-ot yet. Use "Read backend-ot now".</p>
      )}
      {!isLoading && !isError && statuses.length > 0 && (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Site</TableHead>
                <TableHead>AI access</TableHead>
                <TableHead>Pending changes</TableHead>
                <TableHead>Approved</TableHead>
                <TableHead>Last read from backend-ot</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {statuses.map(status => <StatusRow key={status.site_id} status={status} timeZone={timeZoneOf(status.site_id)} />)}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function StatusRow({ status, timeZone }: { status: SiteProfileStatus; timeZone: string }) {
  const onboarded = status.approved_version != null;
  return (
    <TableRow>
      <TableCell className="font-medium">
        <div className="flex items-center gap-2">
          <Button asChild variant="outline" size="sm" className="border-primary text-primary hover:bg-primary hover:text-primary-foreground">
            <Link to={`/site-profiles/${status.site_id}?tab=knowledge`} aria-label={`Open the knowledge base of ${status.name}`}>
              <BookOpen className="w-4 h-4 mr-2" />{status.name}<ChevronRight className="w-4 h-4 ml-1" />
            </Link>
          </Button>
          <span className="text-muted-foreground">#{status.site_id}</span>
        </div>
      </TableCell>
      <TableCell>
        {onboarded
          ? <Badge variant="outline" className="bg-success/10 text-success border-success">Onboarded · v{status.approved_version}</Badge>
          : <Badge variant="outline" className="text-muted-foreground">Not onboarded</Badge>}
      </TableCell>
      <TableCell>
        {status.pending_changes > 0
          ? <Link to={`/site-profiles/${status.site_id}?tab=changes`}><Badge variant="secondary">{status.pending_changes} to review</Badge></Link>
          : <span className="text-muted-foreground">None</span>}
      </TableCell>
      <TableCell className="whitespace-nowrap">{formatDateTime(status.approved_at, timeZone)}</TableCell>
      <TableCell className="whitespace-nowrap">{formatDateTime(status.fetched_at, timeZone)}</TableCell>
    </TableRow>
  );
}
