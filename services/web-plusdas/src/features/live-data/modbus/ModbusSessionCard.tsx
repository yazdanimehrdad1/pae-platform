import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Copy, RotateCw, Square, Trash2 } from "lucide-react";
import { RegisterValuesTable } from "./RegisterValuesTable";
import { toast } from "@/shared/hooks/use-toast";
import type { ModbusSessionState } from "@/shared/types/modbusLiveStream";

const ATTACHMENT_STYLES: Record<string, string> = {
  connecting: "bg-warning/10 text-warning border-warning",
  streaming: "bg-success/10 text-success border-success",
  error: "bg-destructive/10 text-destructive border-destructive",
};

const SERVER_STATUS_STYLES: Record<string, string> = {
  active: "bg-muted text-muted-foreground border-border",
  stopped: "bg-secondary text-secondary-foreground border-border",
  done: "bg-secondary text-secondary-foreground border-border",
};

export function getDisplayStatus(session: ModbusSessionState): { label: string; className: string } {
  if (session.attachment !== 'idle') {
    return { label: session.attachment, className: ATTACHMENT_STYLES[session.attachment] };
  }
  return {
    label: session.serverStatus,
    className: SERVER_STATUS_STYLES[session.serverStatus] ?? "bg-muted text-muted-foreground border-border",
  };
}

function ConfigField({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <span className="text-xs text-muted-foreground block">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function ModbusSessionCard({ session, alias, onResume, onStop, onDelete }: {
  session: ModbusSessionState;
  alias?: string;
  onResume: () => void;
  onStop: () => void;
  onDelete: () => void;
}) {
  const canResume = session.attachment === 'idle' || session.attachment === 'error';
  const canStop = session.serverStatus === 'active';
  const displayStatus = getDisplayStatus(session);

  const handleCopySessionId = () => {
    navigator.clipboard.writeText(session.sessionId);
    toast({ title: "Session ID copied" });
  };

  return (
    <Card className="border-2">
      <CardHeader className="pb-3 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold">Session {session.slot}{alias && <span className="text-muted-foreground font-normal"> · {alias}</span>}</h3>
            <Badge variant="outline" className={displayStatus.className}>{displayStatus.label}</Badge>
            <span className="text-sm text-muted-foreground">{session.host}:{session.port}</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="gap-1" onClick={onResume} disabled={!canResume}>
              <RotateCw className="w-3 h-3" />Resume
            </Button>
            <Button variant="outline" size="sm" className="gap-1" onClick={onStop} disabled={!canStop}>
              <Square className="w-3 h-3" />Stop
            </Button>
            <Button variant="outline" size="sm" className="gap-1 text-destructive hover:text-destructive" onClick={onDelete}>
              <Trash2 className="w-3 h-3" />Delete
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-1.5 rounded-md bg-muted/50 px-2.5 py-1.5">
          <span className="text-xs text-muted-foreground">Session ID:</span>
          <span className="text-sm font-mono">{session.sessionId}</span>
          <Button variant="ghost" size="icon" className="h-5 w-5" onClick={handleCopySessionId}>
            <Copy className="w-3 h-3" />
          </Button>
        </div>

        <div className="text-xs text-muted-foreground">
          {session.startedAt && <>Started {new Date(session.startedAt).toLocaleTimeString()} · </>}
          Poll #{session.pollCount}
          {session.lastTimestamp && <> · last update {new Date(session.lastTimestamp).toLocaleTimeString()}</>}
        </div>
        {session.error && <p className="text-xs text-destructive">{session.error}</p>}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-md border border-border bg-muted/30 p-3 space-y-2">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Configuration</h4>
          <div className="grid grid-cols-4 gap-3">
            <ConfigField label="Host" value={session.host} />
            <ConfigField label="Port" value={session.port} />
            <ConfigField label="Server Address" value={session.server_address} />
            <ConfigField label="Kind" value={session.kind} />
            <ConfigField label="Address Range" value={`${session.start_address}–${session.end_address}`} />
            <ConfigField label="Address Mode" value={session.modbus_address_mode} />
            <ConfigField label="Interval" value={`${session.interval}s`} />
            <ConfigField label="Duration" value={`${session.duration}s`} />
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Live Registers</h4>
          <RegisterValuesTable registerConfigs={session.registerConfigs} registers={session.registers} />
        </div>
      </CardContent>
    </Card>
  );
}
