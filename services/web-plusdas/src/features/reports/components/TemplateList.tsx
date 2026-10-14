import { Link } from "react-router-dom";
import { CalendarClock, FileText, Pencil, Play } from "lucide-react";
import type { ReportTemplateRecord } from "@/api/types/reports";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { windowLabel } from "../lib/format";

/** The site's report templates: Generate queues a report as the template says; Customize opens it
 * in the builder (another period or other points, or changes to save). */
export function TemplateList({ siteId, templates, isLoading, generatingId, onGenerate, onSchedule }: {
  siteId: string;
  templates: ReportTemplateRecord[];
  isLoading: boolean;
  generatingId: number | null;
  onGenerate: (template: ReportTemplateRecord) => void;
  onSchedule: (template: ReportTemplateRecord) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Templates</CardTitle>
        <CardDescription>What a report contains and the period it covers. Generate one to get a report.</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading templates...</p>
        ) : templates.length === 0 ? (
          <p className="text-sm text-muted-foreground">No report templates for this site yet. Build one with New report.</p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {templates.map(template => (
              <li key={template.id} className="flex flex-col justify-between gap-3 rounded-lg border border-border p-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <FileText aria-hidden className="h-4 w-4 shrink-0 text-primary" />
                    <h3 className="font-medium">{template.name}</h3>
                  </div>
                  {template.description && <p className="text-sm text-muted-foreground">{template.description}</p>}
                  <p className="text-xs text-muted-foreground">
                    {windowLabel(template.definition.window)} · {template.definition.blocks.length} section{template.definition.blocks.length === 1 ? "" : "s"}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="gap-1.5"
                    disabled={generatingId === template.id}
                    onClick={() => onGenerate(template)}
                    aria-label={`Generate ${template.name}`}
                  >
                    <Play aria-hidden className="h-3.5 w-3.5" />
                    {generatingId === template.id ? "Queuing..." : "Generate"}
                  </Button>
                  <Button asChild size="sm" variant="ghost" className="gap-1.5">
                    <Link to={`/reports/${siteId}/builder?template=${template.id}`} aria-label={`Customize ${template.name}`}>
                      <Pencil aria-hidden className="h-3.5 w-3.5" />Customize
                    </Link>
                  </Button>
                  <Button size="sm" variant="ghost" className="gap-1.5" onClick={() => onSchedule(template)} aria-label={`Schedule ${template.name}`}>
                    <CalendarClock aria-hidden className="h-3.5 w-3.5" />Schedule
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
