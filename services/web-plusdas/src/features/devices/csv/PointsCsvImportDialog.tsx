import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { devicesApi } from "@/api/devices";
import { getErrorMessage } from "@/api/client";
import type { PointsCsvImportResult } from "@/api/types/devicePoints";
import { toast } from "@/shared/hooks/use-toast";

export interface CsvFile {
  name: string;
  text: string;
  id: number; // a new id per pick, so the same file picked again is checked again
}

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;

function NameList({ title, names }: { title: string; names: string[] }) {
  if (names.length === 0) return null;
  return (
    <div className="space-y-1">
      <h4 className="text-sm font-medium">{title}</h4>
      <p className="text-sm text-muted-foreground break-words">{names.join(", ")}</p>
    </div>
  );
}

function Plan({ plan, deleteMissing, onDeleteMissingChange }: {
  plan: PointsCsvImportResult;
  deleteMissing: boolean;
  onDeleteMissingChange: (value: boolean) => void;
}) {
  return (
    <div className="space-y-4">
      <NameList title={`New (${plan.created.length})`} names={plan.created} />
      <NameList
        title={`Changed (${plan.updated.length})`}
        names={plan.updated.map(change => `${change.name} (${change.fields.join(", ")})`)}
      />
      {plan.unchanged.length > 0 && (
        <p className="text-sm text-muted-foreground">{plural(plan.unchanged.length, "point")} unchanged.</p>
      )}
      {plan.missing.length > 0 && (
        <div className="space-y-2 rounded-md border p-3">
          <NameList title={`Not in the file (${plan.missing.length})`} names={plan.missing} />
          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={deleteMissing} onCheckedChange={value => onDeleteMissingChange(value === true)}
              aria-label="Delete these" />
            Delete these
          </label>
          <p className="text-xs text-muted-foreground">
            Deleted points move to the Deleted tab, where they can be restored. Left unticked, they stay as they are.
          </p>
        </div>
      )}
    </div>
  );
}

function Problems({ plan }: { plan: PointsCsvImportResult }) {
  return (
    <div className="space-y-2">
      <p className="flex items-center gap-2 text-sm text-destructive">
        <AlertTriangle className="w-4 h-4" />
        {plural(plan.errors.length, "problem")} in the file. Fix {plan.errors.length === 1 ? "it" : "them"} and
        import the file again; nothing has changed.
      </p>
      <div className="max-h-72 overflow-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">Line</TableHead>
              <TableHead className="w-28">Column</TableHead>
              <TableHead>Problem</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {plan.errors.map((error, index) => (
              <TableRow key={index}>
                <TableCell>{error.line ?? "–"}</TableCell>
                <TableCell>{error.column ?? "–"}</TableCell>
                <TableCell>{error.message}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

/** The preview of a CSV import: backend-ot checks the file (a dry run) and says what it would add,
 * change and leave out; Apply imports it in one go. */
export function PointsCsvImportDialog({ file, siteId, deviceId, onClose, onImported }: {
  file: CsvFile;
  siteId: string;
  deviceId: number;
  onClose: () => void;
  onImported: () => void;
}) {
  const [deleteMissing, setDeleteMissing] = useState(false);
  // Checked again when the choice changes: a point that stays can clash with a row of the file.
  const planQuery = useQuery({
    queryKey: ["points-csv-plan", siteId, deviceId, file.id, deleteMissing],
    queryFn: () => devicesApi.importPointsCsv(siteId, deviceId, file.text, { dryRun: true, deleteMissing }),
    gcTime: 0,
    retry: false,
    placeholderData: previous => previous,
  });
  const plan = planQuery.data;

  const apply = useMutation({
    mutationFn: () => devicesApi.importPointsCsv(siteId, deviceId, file.text, { dryRun: false, deleteMissing }),
    onSuccess: result => {
      onImported();
      toast({
        title: "Points imported",
        description: [
          [result.created.length, "added"] as const,
          [result.updated.length, "updated"] as const,
          [result.deleted.length, "deleted"] as const,
        ].filter(([count]) => count > 0).map(([count, verb]) => `${plural(count, "point")} ${verb}`).join(", "),
      });
      onClose();
    },
    onError: error => {
      toast({ title: "Import failed", description: getErrorMessage(error), variant: "destructive" });
    },
  });

  const hasProblems = (plan?.errors.length ?? 0) > 0;
  const changes = plan
    ? plan.created.length + plan.updated.length + (deleteMissing ? plan.missing.length : 0)
    : 0;
  const canApply = !!plan && !hasProblems && changes > 0 && !planQuery.isFetching && !apply.isPending;

  return (
    <Dialog open onOpenChange={open => { if (!open && !apply.isPending) onClose(); }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Import points from CSV</DialogTitle>
          <DialogDescription>{file.name}: nothing changes until you apply.</DialogDescription>
        </DialogHeader>

        <div className="max-h-[60vh] overflow-y-auto">
          {planQuery.isError ? (
            <p className="text-sm text-destructive">
              The file can't be checked: {getErrorMessage(planQuery.error)}
            </p>
          ) : !plan ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" />Checking the file…
            </p>
          ) : hasProblems ? (
            <Problems plan={plan} />
          ) : (
            <Plan plan={plan} deleteMissing={deleteMissing} onDeleteMissingChange={setDeleteMissing} />
          )}
          {plan && !hasProblems && changes === 0 && (
            <p className="mt-3 text-sm text-muted-foreground">The file matches the device: nothing to import.</p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={apply.isPending}>Cancel</Button>
          <Button onClick={() => apply.mutate()} disabled={!canApply}>
            {apply.isPending && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
