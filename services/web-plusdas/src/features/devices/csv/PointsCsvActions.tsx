import { useRef, useState } from "react";
import { Download, FileSpreadsheet, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { devicesApi } from "@/api/devices";
import { getErrorMessage } from "@/api/client";
import { useAuth, type UserRole } from "@/shared/contexts/auth";
import { toast } from "@/shared/hooks/use-toast";
import { downloadFile, fileName } from "@/shared/lib/download";
import { PointsCsvImportDialog, type CsvFile } from "./PointsCsvImportDialog";

const CSV_MIME = "text/csv;charset=utf-8";
// Who may change points from a file; everyone can download the template and the export.
const CSV_IMPORT_ROLES: readonly UserRole[] = ["admin", "engineer"];

/** The device's points as a CSV: an empty template, the current points, and an import (previewed
 * before anything changes). backend-ot builds, checks and applies the files. */
export function PointsCsvActions({ siteId, deviceId, deviceName, disabled, onImported }: {
  siteId: string;
  deviceId: number;
  deviceName: string;
  disabled?: boolean;
  onImported: () => void;
}) {
  const { user } = useAuth();
  const canImport = !!user && CSV_IMPORT_ROLES.includes(user.role);
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<CsvFile | null>(null);
  const [busy, setBusy] = useState<"template" | "export" | null>(null);

  const download = async (kind: "template" | "export") => {
    setBusy(kind);
    try {
      const content = kind === "template"
        ? await devicesApi.pointsCsvTemplate()
        : await devicesApi.exportPointsCsv(siteId, deviceId);
      const name = kind === "template" ? "device-points-template" : fileName(deviceName, "points");
      downloadFile(`${name}.csv`, content, CSV_MIME);
    } catch (error) {
      toast({ title: "Download failed", description: getErrorMessage(error), variant: "destructive" });
    } finally {
      setBusy(null);
    }
  };

  const pick = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const picked = event.target.files?.[0];
    event.target.value = ""; // the same file can be picked again after an edit
    if (!picked) return;
    try {
      setFile({ name: picked.name, text: await picked.text(), id: Date.now() });
    } catch (error) {
      toast({ title: "Can't read the file", description: getErrorMessage(error), variant: "destructive" });
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="outline" size="sm" className="gap-1" disabled={busy !== null}
        onClick={() => void download("template")} title="An empty CSV with the columns to fill in">
        <FileSpreadsheet className="w-4 h-4" />Template
      </Button>
      <Button variant="outline" size="sm" className="gap-1" disabled={disabled || busy !== null}
        onClick={() => void download("export")} title="This device's points as CSV, to edit and import">
        <Download className="w-4 h-4" />Export CSV
      </Button>
      {canImport && (
        <>
          <Button variant="outline" size="sm" className="gap-1" disabled={disabled}
            onClick={() => fileInput.current?.click()} title="Add or update points from a CSV (previewed first)">
            <Upload className="w-4 h-4" />Import CSV
          </Button>
          <input ref={fileInput} type="file" accept=".csv,text/csv" className="hidden"
            aria-label="CSV file to import" onChange={event => void pick(event)} />
        </>
      )}
      {file && (
        <PointsCsvImportDialog
          key={file.id}
          file={file}
          siteId={siteId}
          deviceId={deviceId}
          onClose={() => setFile(null)}
          onImported={onImported}
        />
      )}
    </div>
  );
}
