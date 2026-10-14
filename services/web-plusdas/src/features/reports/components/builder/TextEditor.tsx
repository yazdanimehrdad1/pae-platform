import { useRef, useState } from "react";
import { Plus } from "lucide-react";
import type { ReportBlock } from "@/api/types/reports";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { UNSET_POINT } from "../../lib/draft";
import { deviceToken, insertAt, pointToken, previewText, siteToken } from "../../lib/textVariables";
import type { BuilderOptions } from "../../types";
import { PointPicker } from "./PointPicker";

type TextBlock = Extract<ReportBlock, { kind: "text" }>;

/** A text section: its body, an Insert menu for the site's, a device's or a point's variables
 * (added where the cursor is), and a preview of how it will read. */
export function TextEditor({ block, options, onChange }: { block: TextBlock; options: BuilderOptions; onChange: (block: TextBlock) => void }) {
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const [siteVariable, setSiteVariable] = useState("");
  const [deviceId, setDeviceId] = useState<number | null>(null);
  const [deviceField, setDeviceField] = useState("name");
  const [pointId, setPointId] = useState(UNSET_POINT);
  const [pointField, setPointField] = useState("name");
  const variables = options.textVariables;

  const insert = (token: string) => {
    const textArea = textAreaRef.current;
    const { body, caret } = insertAt(block.body, token, textArea?.selectionStart ?? block.body.length, textArea?.selectionEnd ?? block.body.length);
    onChange({ ...block, body });
    requestAnimationFrame(() => {
      textArea?.focus();
      textArea?.setSelectionRange(caret, caret);
    });
  };
  const preview = previewText(block.body, { siteName: options.siteName, variables, devices: options.devices, points: options.points });

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label htmlFor={`${block.id}-body`}>Text</Label>
        <Textarea ref={textAreaRef} id={`${block.id}-body`} rows={3} value={block.body} maxLength={5000} onChange={event => onChange({ ...block, body: event.target.value })} />
      </div>

      <fieldset className="space-y-2 rounded-md border border-border p-3">
        <legend className="px-1 text-sm font-medium">Insert a variable</legend>
        <div className="flex flex-wrap items-center gap-2">
          <span className="w-14 text-xs text-muted-foreground">Site</span>
          <Select value={siteVariable || undefined} onValueChange={setSiteVariable}>
            <SelectTrigger aria-label="Site variable" className="w-64"><SelectValue placeholder="Choose a site variable" /></SelectTrigger>
            <SelectContent>
              {(variables.site ?? []).map(variable => <SelectItem key={variable.name} value={variable.name}>{variable.description}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button type="button" size="sm" variant="outline" className="gap-1" disabled={!siteVariable} onClick={() => insert(siteToken(siteVariable))}>
            <Plus aria-hidden className="h-3.5 w-3.5" />Insert
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="w-14 text-xs text-muted-foreground">Device</span>
          <Select value={deviceId ? String(deviceId) : undefined} onValueChange={value => setDeviceId(Number(value))}>
            <SelectTrigger aria-label="Device" className="w-64"><SelectValue placeholder="Choose a device" /></SelectTrigger>
            <SelectContent>
              {options.devices.map(device => <SelectItem key={device.deviceId} value={String(device.deviceId)}>{device.deviceName}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={deviceField} onValueChange={setDeviceField}>
            <SelectTrigger aria-label="Device field" className="w-36"><SelectValue /></SelectTrigger>
            <SelectContent>
              {(variables.device_fields ?? []).map(variable => <SelectItem key={variable.name} value={variable.name}>{variable.description}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button type="button" size="sm" variant="outline" className="gap-1" disabled={deviceId === null} onClick={() => deviceId !== null && insert(deviceToken(deviceId, deviceField))}>
            <Plus aria-hidden className="h-3.5 w-3.5" />Insert
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="w-14 text-xs text-muted-foreground">Point</span>
          <div className="w-64"><PointPicker options={options.points} pointId={pointId} onChange={setPointId} ariaLabel="Point" /></div>
          <Select value={pointField} onValueChange={setPointField}>
            <SelectTrigger aria-label="Point field" className="w-56"><SelectValue /></SelectTrigger>
            <SelectContent>
              {(variables.point_fields ?? []).map(variable => <SelectItem key={variable.name} value={variable.name}>{variable.description}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button type="button" size="sm" variant="outline" className="gap-1" disabled={pointId === UNSET_POINT} onClick={() => insert(pointToken(pointId, pointField))}>
            <Plus aria-hidden className="h-3.5 w-3.5" />Insert
          </Button>
        </div>
      </fieldset>

      {block.body.trim() && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">Preview</p>
          <p className="whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-sm" aria-label={`${block.id} preview`}>{preview}</p>
          <p className="text-xs text-muted-foreground">‹…› values are computed when the report is generated, for its period.</p>
        </div>
      )}
    </div>
  );
}
