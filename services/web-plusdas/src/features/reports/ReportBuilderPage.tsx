import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Play, Plus, Save, Trash2 } from "lucide-react";
import { sitesApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import type { ReportDefinition, ReportTemplateRecord } from "@/api/types/reports";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { devicePointOptions } from "@/shared/components/conditions/devicePointOptions";
import { toast } from "@/shared/hooks/use-toast";
import { BlockEditor } from "./components/builder/BlockEditor";
import { WindowEditor } from "./components/builder/WindowEditor";
import { useBuilderMutations, useReportCatalog, useReportTemplate, useSiteDevicePoints } from "./hooks/useReports";
import {
  BLOCK_KIND_LABELS,
  blankDefinition,
  draftProblems,
  errorsByBlock,
  LIMITS,
  moveBlock,
  newBlock,
  runRequest,
  validationErrors,
  type BlockKind,
} from "./lib/draft";
import type { BuilderOptions } from "./types";

/**
 * Build a report: a blank one, or a template (?template=<id>) to change or to generate with a
 * custom period. Generate queues it and opens it; Save keeps it as a template.
 */
export default function ReportBuilderPage() {
  const { siteId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const templateId = searchParams.get("template") ? Number(searchParams.get("template")) : null;
  const template = useReportTemplate(siteId, templateId);

  if (templateId !== null && template.isLoading) return <p className="p-6 text-sm text-muted-foreground">Loading template...</p>;
  if (templateId !== null && (template.error || !template.data)) {
    return <p role="alert" className="p-6 text-sm text-destructive">{template.error ? getErrorMessage(template.error) : "Template not found"}</p>;
  }
  // Keyed by template, so opening another template starts from its definition.
  return <Builder key={templateId ?? "new"} siteId={siteId} template={template.data ?? null} />;
}

function Builder({ siteId, template }: { siteId: string; template: ReportTemplateRecord | null }) {
  const navigate = useNavigate();
  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: sitesApi.getAll });
  const site = sites.find(candidate => candidate.id === siteId);
  const catalog = useReportCatalog(siteId);
  const devices = useSiteDevicePoints(siteId);
  const { requestRun, createTemplate, updateTemplate, deleteTemplate } = useBuilderMutations(siteId);

  const [definition, setDefinition] = useState<ReportDefinition>(() => structuredClone(template?.definition ?? blankDefinition()));
  const [name, setName] = useState(template?.name ?? "");
  const [description, setDescription] = useState(template?.description ?? "");
  const [serverErrors, setServerErrors] = useState<string[]>([]);

  const timeZone = catalog.data?.timezone ?? site?.timezone ?? "UTC";
  const options: BuilderOptions = useMemo(() => ({
    points: devicePointOptions(devices.data ?? [], { includeVirtual: true }),
    devices: devices.data ?? [],
    functions: catalog.data?.site_functions ?? [],
    textVariables: catalog.data?.text_variables ?? {},
    siteName: site?.name ?? `Site ${siteId}`,
    timeZone,
  }), [devices.data, catalog.data, timeZone, site?.name, siteId]);

  const problems = draftProblems(definition);
  const blockIds = definition.blocks.map(block => block.id);
  const { general, byBlock } = errorsByBlock(serverErrors, blockIds);
  const canSend = problems.size === 0;
  const isBusy = requestRun.isPending || createTemplate.isPending || updateTemplate.isPending;

  useEffect(() => setServerErrors([]), [definition]);

  const edit = (next: ReportDefinition) => setDefinition(next);
  const setBlock = (index: number, block: ReportDefinition["blocks"][number]) =>
    edit({ ...definition, blocks: definition.blocks.map((current, position) => (position === index ? block : current)) });
  const addBlock = (kind: BlockKind) => edit({ ...definition, blocks: [...definition.blocks, newBlock(kind, definition.blocks)] });

  const onFailure = (title: string) => (error: unknown) => {
    const errors = validationErrors(error);
    setServerErrors(errors);
    toast({ title, description: errors.length > 0 ? "Fix the sections marked below." : getErrorMessage(error), variant: "destructive" });
  };

  const generate = () =>
    requestRun.mutate(runRequest(definition, template, name), {
      onSuccess: run => navigate(`/reports/${siteId}/runs/${run.id}`),
      onError: onFailure("Could not generate the report"),
    });
  const saveAsNew = () =>
    createTemplate.mutate({ name: name.trim(), description, definition }, {
      onSuccess: created => {
        toast({ title: "Template saved", description: `"${created.name}" is in the site's templates.` });
        navigate(`/reports/${siteId}/builder?template=${created.id}`, { replace: true });
      },
      onError: onFailure("Could not save the template"),
    });
  const save = () => {
    if (!template) return saveAsNew();
    updateTemplate.mutate({ templateId: template.id, payload: { name: name.trim(), description, definition } }, {
      onSuccess: saved => toast({ title: "Template saved", description: `"${saved.name}", version ${saved.version}.` }),
      onError: onFailure("Could not save the template"),
    });
  };
  const remove = () =>
    template && deleteTemplate.mutate(template.id, {
      onSuccess: () => {
        toast({ title: "Template deleted", description: "Reports already generated from it stay." });
        navigate(`/reports?site=${siteId}`);
      },
      onError: onFailure("Could not delete the template"),
    });

  const hasName = name.trim().length > 0;
  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <div className="space-y-1">
        <Button asChild variant="ghost" size="sm" className="-ml-2 gap-1.5">
          <Link to={`/reports?site=${siteId}`}><ArrowLeft aria-hidden className="h-4 w-4" />Reports</Link>
        </Button>
        <h1 className="text-2xl font-semibold">{template ? `Template: ${template.name}` : "New report"}</h1>
        <p className="text-sm text-muted-foreground">
          {site?.name ?? `Site ${siteId}`} · times in {timeZone}
          {template && ` · version ${template.version}`}
        </p>
      </div>

      <Card>
        <CardHeader><CardTitle>Report</CardTitle></CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="report-name">Name</Label>
            <Input id="report-name" value={name} maxLength={150} placeholder="e.g. Daily energy" onChange={event => setName(event.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="report-description">Description</Label>
            <Textarea id="report-description" rows={1} value={description} maxLength={2000} onChange={event => setDescription(event.target.value)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Period</CardTitle>
          <CardDescription>The time the report covers.</CardDescription>
        </CardHeader>
        <CardContent>
          <WindowEditor window={definition.window} timeZone={timeZone} problems={problems.get("window") ?? []} onChange={window => edit({ ...definition, window })} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sections</CardTitle>
          <CardDescription>In the order they appear in the report.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {(devices.error || catalog.error) && (
            <p role="alert" className="text-sm text-destructive">{getErrorMessage(devices.error ?? catalog.error)}</p>
          )}
          {definition.blocks.map((block, index) => (
            <BlockEditor
              key={block.id}
              block={block}
              position={index}
              count={definition.blocks.length}
              options={options}
              problems={[...(problems.get(block.id) ?? []), ...(byBlock.get(block.id) ?? [])]}
              onChange={changed => setBlock(index, changed)}
              onMove={delta => edit({ ...definition, blocks: moveBlock(definition.blocks, index, delta) })}
              onRemove={() => edit({ ...definition, blocks: definition.blocks.filter((_, position) => position !== index) })}
            />
          ))}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="gap-1.5" disabled={definition.blocks.length >= LIMITS.blocks}>
                <Plus aria-hidden className="h-3.5 w-3.5" />Add section
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {(Object.keys(BLOCK_KIND_LABELS) as BlockKind[]).map(kind => (
                <DropdownMenuItem key={kind} onSelect={() => addBlock(kind)}>{BLOCK_KIND_LABELS[kind]}</DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </CardContent>
      </Card>

      {general.length > 0 && (
        <ul role="alert" className="space-y-1">{general.map(error => <li key={error} className="text-sm text-destructive">{error}</li>)}</ul>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button className="gap-1.5" disabled={!canSend || isBusy} onClick={generate}>
          <Play aria-hidden className="h-4 w-4" />Generate report
        </Button>
        <Button variant="outline" className="gap-1.5" disabled={!canSend || !hasName || isBusy} onClick={save}>
          <Save aria-hidden className="h-4 w-4" />{template ? "Save template" : "Save as template"}
        </Button>
        {template && (
          <Button variant="outline" disabled={!canSend || !hasName || isBusy} onClick={saveAsNew}>Save as new template</Button>
        )}
        {template && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" className="ml-auto gap-1.5 text-destructive"><Trash2 aria-hidden className="h-4 w-4" />Delete template</Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete "{template.name}"?</AlertDialogTitle>
                <AlertDialogDescription>Reports already generated from it stay.</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={remove}>Delete</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </div>
      {!canSend && <p className="text-xs text-muted-foreground">Fill in the sections marked in red to generate or save.</p>}
      {canSend && !hasName && <p className="text-xs text-muted-foreground">Give the report a name to save it as a template.</p>}
    </div>
  );
}
