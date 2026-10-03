import { useState, type ReactNode, type SelectHTMLAttributes } from "react";
import { Crosshair, Plus, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import type { DeviceRecord } from "@/api/types/devices";
import type { SiteSld, SldDeviceLink, SldNodeType } from "@/api/types/sld";
import {
  addBus,
  addNode,
  connect,
  connectedTo,
  disconnect,
  moveElement,
  removeElement,
  rolesForType,
  updateBus,
  updateNode,
  type Cell,
} from "../lib/sldDraft";
import { INFO_ROWS } from "../lib/sldInfoRows";
import { NODE_TYPE_LABELS } from "../lib/sldNodeTypes";

const NONE = "";

export type PickTarget = "element" | "cell";

// Asks the page to take the next click on the diagram (an element or an empty cell).
export type RequestPick = (target: PickTarget, label: string, onPicked: (value: string | Cell) => void) => void;

interface SldEditorPanelProps {
  draft: SiteSld;
  onChange: (draft: SiteSld) => void;
  devices: DeviceRecord[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  selectedCell: Cell | null;
  onClearCell: () => void;
  requestPick: RequestPick;
  errors: string[];
}

// A native select styled like the inputs: dense, keyboard friendly and testable.
function NativeSelect(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className="flex h-9 w-full rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
    />
  );
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <Label htmlFor={htmlFor} className="text-xs">
        {label}
      </Label>
      {children}
    </div>
  );
}

function elementOptions(draft: SiteSld, exceptId?: string) {
  return [
    ...draft.nodes.map((node) => ({ id: node.id, label: `${node.name} (${NODE_TYPE_LABELS[node.type]})` })),
    ...(draft.buses ?? []).map((bus) => ({ id: bus.id, label: `${bus.name} (bus)` })),
  ].filter((option) => option.id !== exceptId);
}

function nameOf(draft: SiteSld, id: string): string {
  return draft.nodes.find((node) => node.id === id)?.name ?? (draft.buses ?? []).find((bus) => bus.id === id)?.name ?? id;
}

/** "Fed from" / "Connect to": a list of the diagram's elements, or pick one on the diagram. */
function ElementPicker({
  id,
  label,
  draft,
  value,
  exceptId,
  onChange,
  requestPick,
}: {
  id: string;
  label: string;
  draft: SiteSld;
  value: string;
  exceptId?: string;
  onChange: (id: string) => void;
  requestPick: RequestPick;
}) {
  return (
    <Field label={label} htmlFor={id}>
      <div className="flex gap-2">
        <NativeSelect id={id} value={value} onChange={(event) => onChange(event.target.value)}>
          <option value={NONE}>— none —</option>
          {elementOptions(draft, exceptId).map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </NativeSelect>
        <Button
          type="button"
          variant="outline"
          size="icon"
          title="Pick on the diagram"
          aria-label={`${label}: pick on the diagram`}
          onClick={() => requestPick("element", label, (picked) => onChange(picked as string))}
        >
          <Crosshair className="w-4 h-4" />
        </Button>
      </div>
    </Field>
  );
}

/** The backend device an element shows values of, and which point fills each of its fields. */
function DeviceLinkFields({
  idPrefix,
  type,
  link,
  devices,
  onChange,
}: {
  idPrefix: string;
  type: SldNodeType;
  link: SldDeviceLink | null | undefined;
  devices: DeviceRecord[];
  onChange: (link: SldDeviceLink | null) => void;
}) {
  const roles = rolesForType(type);
  if (roles.length === 0) return null;
  const device = devices.find((candidate) => candidate.device_id === link?.device_id);
  const points = device ? [...device.points.native, ...device.points.virtual, ...device.points.standardized] : [];
  const roleLabel = (role: string) =>
    INFO_ROWS[type]?.find((row) => row.kind === "value" && row.role === role)?.label ?? role;

  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <Field label="Device" htmlFor={`${idPrefix}-device`}>
        <NativeSelect
          id={`${idPrefix}-device`}
          value={link ? String(link.device_id) : NONE}
          onChange={(event) =>
            onChange(event.target.value === NONE ? null : { device_id: Number(event.target.value), points: {} })
          }
        >
          <option value={NONE}>— not linked —</option>
          {devices.map((candidate) => (
            <option key={candidate.device_id} value={candidate.device_id}>
              {candidate.name} ({candidate.type})
            </option>
          ))}
        </NativeSelect>
      </Field>
      {link &&
        roles.map((role) => (
          <Field key={role} label={roleLabel(role)} htmlFor={`${idPrefix}-role-${role}`}>
            <NativeSelect
              id={`${idPrefix}-role-${role}`}
              value={link.points?.[role] !== undefined ? String(link.points[role]) : NONE}
              onChange={(event) => {
                const nextPoints = { ...(link.points ?? {}) };
                if (event.target.value === NONE) delete nextPoints[role];
                else nextPoints[role] = Number(event.target.value);
                onChange({ ...link, points: nextPoints });
              }}
            >
              <option value={NONE}>— none (shows NA) —</option>
              {points.map((point) => (
                <option key={point.id} value={point.id}>
                  {point.unit ? `${point.name} (${point.unit})` : point.name}
                </option>
              ))}
            </NativeSelect>
          </Field>
        ))}
    </div>
  );
}

const EMPTY_NODE_FORM = {
  type: "breaker" as SldNodeType,
  name: "",
  voltage: "",
  rating: "",
  upstreamId: NONE,
  device: null as SldDeviceLink | null,
};

function AddElementForm({
  draft,
  onChange,
  devices,
  selectedCell,
  onClearCell,
  onAdded,
  requestPick,
}: Pick<SldEditorPanelProps, "draft" | "onChange" | "devices" | "selectedCell" | "onClearCell" | "requestPick"> & {
  onAdded: (id: string) => void;
}) {
  const [form, setForm] = useState(EMPTY_NODE_FORM);
  const canAdd = form.name.trim().length > 0;

  const submit = () => {
    const result = addNode(draft, {
      type: form.type,
      name: form.name,
      voltage: form.voltage,
      rating: form.rating,
      device: form.device,
      upstreamId: form.upstreamId || null,
      cell: selectedCell,
    });
    onChange(result.draft);
    setForm(EMPTY_NODE_FORM);
    onClearCell();
    onAdded(result.id);
  };

  return (
    <div className="space-y-3">
      <Field label="Type" htmlFor="add-type">
        <NativeSelect
          id="add-type"
          value={form.type}
          onChange={(event) => setForm({ ...form, type: event.target.value as SldNodeType, device: null })}
        >
          {Object.entries(NODE_TYPE_LABELS).map(([type, label]) => (
            <option key={type} value={type}>
              {label}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Name" htmlFor="add-name">
        <Input id="add-name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Voltage" htmlFor="add-voltage">
          <Input
            id="add-voltage"
            placeholder="34.5 kV"
            value={form.voltage}
            onChange={(event) => setForm({ ...form, voltage: event.target.value })}
          />
        </Field>
        <Field label="Rating" htmlFor="add-rating">
          <Input
            id="add-rating"
            placeholder="2 MW"
            value={form.rating}
            onChange={(event) => setForm({ ...form, rating: event.target.value })}
          />
        </Field>
      </div>
      <ElementPicker
        id="add-upstream"
        label="Fed from"
        draft={draft}
        value={form.upstreamId}
        onChange={(upstreamId) => setForm((previous) => ({ ...previous, upstreamId }))}
        requestPick={requestPick}
      />
      <p className="text-xs text-muted-foreground">
        {selectedCell ? (
          <>
            Placed in the selected cell ({selectedCell.col}, {selectedCell.row}).{" "}
            <button type="button" className="underline" onClick={onClearCell}>
              Place automatically
            </button>
          </>
        ) : (
          "Placed below what it is fed from. Click an empty cell to choose the spot."
        )}
      </p>
      <DeviceLinkFields
        idPrefix="add"
        type={form.type}
        link={form.device}
        devices={devices}
        onChange={(device) => setForm((previous) => ({ ...previous, device }))}
      />
      <Button type="button" className="w-full gap-2" disabled={!canAdd} onClick={submit}>
        <Plus className="w-4 h-4" />
        Add element
      </Button>
    </div>
  );
}

function AddBusForm({
  draft,
  onChange,
  selectedCell,
  onClearCell,
  onAdded,
  requestPick,
}: Pick<SldEditorPanelProps, "draft" | "onChange" | "selectedCell" | "onClearCell" | "requestPick"> & {
  onAdded: (id: string) => void;
}) {
  const [form, setForm] = useState({ name: "", voltage: "", upstreamId: NONE, span: "3" });
  const span = Number(form.span);
  const canAdd = form.name.trim().length > 0 && span > 0;

  const submit = () => {
    const result = addBus(draft, {
      name: form.name,
      voltage: form.voltage,
      upstreamId: form.upstreamId || null,
      cell: selectedCell,
      span,
    });
    onChange(result.draft);
    setForm({ name: "", voltage: "", upstreamId: NONE, span: "3" });
    onClearCell();
    onAdded(result.id);
  };

  return (
    <div className="space-y-3">
      <Field label="Bus name" htmlFor="bus-name">
        <Input id="bus-name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Voltage" htmlFor="bus-voltage">
          <Input id="bus-voltage" value={form.voltage} onChange={(event) => setForm({ ...form, voltage: event.target.value })} />
        </Field>
        <Field label="Width (columns)" htmlFor="bus-span">
          <Input
            id="bus-span"
            type="number"
            min={1}
            step={1}
            value={form.span}
            onChange={(event) => setForm({ ...form, span: event.target.value })}
          />
        </Field>
      </div>
      <ElementPicker
        id="bus-upstream"
        label="Bus fed from"
        draft={draft}
        value={form.upstreamId}
        onChange={(upstreamId) => setForm((previous) => ({ ...previous, upstreamId }))}
        requestPick={requestPick}
      />
      <Button type="button" variant="outline" className="w-full gap-2" disabled={!canAdd} onClick={submit}>
        <Plus className="w-4 h-4" />
        Add bus
      </Button>
    </div>
  );
}

function ConnectionsEditor({
  draft,
  id,
  onChange,
  requestPick,
}: Pick<SldEditorPanelProps, "draft" | "onChange" | "requestPick"> & { id: string }) {
  const connections = connectedTo(draft, id);
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium">Connections</p>
      {connections.length === 0 && <p className="text-xs text-muted-foreground">Not connected</p>}
      <ul className="space-y-1">
        {connections.map((otherId) => (
          <li key={otherId} className="flex items-center justify-between text-sm">
            <span>{nameOf(draft, otherId)}</span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              aria-label={`Disconnect ${nameOf(draft, otherId)}`}
              onClick={() => onChange(disconnect(draft, id, otherId))}
            >
              <X className="w-3 h-3" />
            </Button>
          </li>
        ))}
      </ul>
      <ElementPicker
        id={`${id}-connect`}
        label="Connect to"
        draft={draft}
        value={NONE}
        exceptId={id}
        onChange={(otherId) => otherId && onChange(connect(draft, id, otherId))}
        requestPick={requestPick}
      />
    </div>
  );
}

/** The side panel of the SLD editor: add elements and buses, edit or delete the selected one. */
export const SldEditorPanel = (props: SldEditorPanelProps) => {
  const { draft, onChange, devices, selectedId, onSelect, requestPick, errors } = props;
  const [adding, setAdding] = useState<"element" | "bus">("element");
  const node = draft.nodes.find((candidate) => candidate.id === selectedId);
  const bus = (draft.buses ?? []).find((candidate) => candidate.id === selectedId);

  const move = (id: string) =>
    requestPick("cell", "Move to", (cell) => onChange(moveElement(draft, id, cell as Cell)));
  const remove = (id: string) => {
    onChange(removeElement(draft, id));
    onSelect(null);
  };

  return (
    <aside className="w-80 shrink-0 overflow-y-auto rounded-lg border border-border bg-card p-4 space-y-4" aria-label="SLD editor">
      {errors.length > 0 && (
        <ul className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive space-y-1" role="alert">
          {errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      )}

      {node && (
        <section className="space-y-3" aria-label="Selected element">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">{node.name}</h3>
            <Button type="button" variant="ghost" size="sm" onClick={() => onSelect(null)}>
              Done
            </Button>
          </div>
          <Field label="Type" htmlFor="edit-type">
            <NativeSelect
              id="edit-type"
              value={node.type}
              onChange={(event) => onChange(updateNode(draft, node.id, { type: event.target.value as SldNodeType }))}
            >
              {Object.entries(NODE_TYPE_LABELS).map(([type, label]) => (
                <option key={type} value={type}>
                  {label}
                </option>
              ))}
            </NativeSelect>
          </Field>
          <Field label="Name" htmlFor="edit-name">
            <Input id="edit-name" value={node.name} onChange={(event) => onChange(updateNode(draft, node.id, { name: event.target.value }))} />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Voltage" htmlFor="edit-voltage">
              <Input
                id="edit-voltage"
                value={node.voltage ?? ""}
                onChange={(event) => onChange(updateNode(draft, node.id, { voltage: event.target.value || null }))}
              />
            </Field>
            <Field label="Rating" htmlFor="edit-rating">
              <Input
                id="edit-rating"
                value={node.rating ?? ""}
                onChange={(event) => onChange(updateNode(draft, node.id, { rating: event.target.value || null }))}
              />
            </Field>
          </div>
          <DeviceLinkFields
            idPrefix="edit"
            type={node.type}
            link={node.device}
            devices={devices}
            onChange={(device) => onChange(updateNode(draft, node.id, { device }))}
          />
          <ConnectionsEditor draft={draft} id={node.id} onChange={onChange} requestPick={requestPick} />
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" className="flex-1 gap-2" onClick={() => move(node.id)}>
              <Crosshair className="w-4 h-4" />
              Move
            </Button>
            <Button type="button" variant="destructive" size="sm" className="flex-1 gap-2" onClick={() => remove(node.id)}>
              <Trash2 className="w-4 h-4" />
              Delete
            </Button>
          </div>
        </section>
      )}

      {bus && (
        <section className="space-y-3" aria-label="Selected bus">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">{bus.name}</h3>
            <Button type="button" variant="ghost" size="sm" onClick={() => onSelect(null)}>
              Done
            </Button>
          </div>
          <Field label="Bus name" htmlFor="edit-bus-name">
            <Input id="edit-bus-name" value={bus.name} onChange={(event) => onChange(updateBus(draft, bus.id, { name: event.target.value }))} />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Voltage" htmlFor="edit-bus-voltage">
              <Input
                id="edit-bus-voltage"
                value={bus.voltage ?? ""}
                onChange={(event) => onChange(updateBus(draft, bus.id, { voltage: event.target.value || null }))}
              />
            </Field>
            <Field label="Width (columns)" htmlFor="edit-bus-span">
              <Input
                id="edit-bus-span"
                type="number"
                min={1}
                step={1}
                value={bus.col_end - bus.col_start}
                onChange={(event) => {
                  const span = Number(event.target.value);
                  if (span > 0) onChange(updateBus(draft, bus.id, { col_end: bus.col_start + span }));
                }}
              />
            </Field>
          </div>
          <ConnectionsEditor draft={draft} id={bus.id} onChange={onChange} requestPick={requestPick} />
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" className="flex-1 gap-2" onClick={() => move(bus.id)}>
              <Crosshair className="w-4 h-4" />
              Move
            </Button>
            <Button type="button" variant="destructive" size="sm" className="flex-1 gap-2" onClick={() => remove(bus.id)}>
              <Trash2 className="w-4 h-4" />
              Delete
            </Button>
          </div>
        </section>
      )}

      {!node && !bus && (
        <section className="space-y-3" aria-label="Add to the diagram">
          <div className="flex gap-1 rounded-md bg-muted p-1" role="tablist">
            {(["element", "bus"] as const).map((kind) => (
              <button
                key={kind}
                type="button"
                role="tab"
                aria-selected={adding === kind}
                className={`flex-1 rounded px-2 py-1 text-sm ${adding === kind ? "bg-background font-medium shadow-sm" : "text-muted-foreground"}`}
                onClick={() => setAdding(kind)}
              >
                {kind === "element" ? "Add element" : "Add bus"}
              </button>
            ))}
          </div>
          {adding === "element" ? (
            <AddElementForm {...props} onAdded={onSelect} />
          ) : (
            <AddBusForm {...props} onAdded={onSelect} />
          )}
          <Separator />
          <p className="text-xs text-muted-foreground">Click an element on the diagram to edit, connect, move or delete it.</p>
        </section>
      )}
    </aside>
  );
};
