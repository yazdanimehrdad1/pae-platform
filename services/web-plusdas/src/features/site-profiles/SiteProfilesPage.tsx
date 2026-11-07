import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { siteProfilesApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { SiteProfileStatus } from "@/api/types/siteProfiles";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/shared/contexts/auth";
import { toast } from "@/shared/hooks/use-toast";
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
              {statuses.map(status => <StatusRow key={status.site_id} status={status} />)}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function StatusRow({ status }: { status: SiteProfileStatus }) {
  const onboarded = status.approved_version != null;
  return (
    <TableRow>
      <TableCell className="font-medium">
        <Link to={`/site-profiles/${status.site_id}`} className="hover:underline">{status.name}</Link>
        <span className="text-muted-foreground"> #{status.site_id}</span>
      </TableCell>
      <TableCell>
        {onboarded
          ? <Badge variant="outline" className="bg-success/10 text-success border-success">Onboarded · v{status.approved_version}</Badge>
          : <Badge variant="outline" className="text-muted-foreground">Not onboarded</Badge>}
      </TableCell>
      <TableCell>
        {status.pending_changes > 0
          ? <Link to={`/site-profiles/${status.site_id}`}><Badge variant="secondary">{status.pending_changes} to review</Badge></Link>
          : <span className="text-muted-foreground">None</span>}
      </TableCell>
      <TableCell className="whitespace-nowrap">{formatDateTime(status.approved_at)}</TableCell>
      <TableCell className="whitespace-nowrap">{formatDateTime(status.fetched_at)}</TableCell>
    </TableRow>
  );
}
