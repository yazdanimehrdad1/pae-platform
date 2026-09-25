import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getDisplayStatus } from "./ModbusSessionCard";
import type { ModbusSessionState } from "@/shared/types/modbusLiveStream";

export function ModbusSessionsOverview({ sessions, aliasBySlot, onSelect }: {
  sessions: ModbusSessionState[];
  aliasBySlot: Record<number, string>;
  onSelect: (sessionId: string) => void;
}) {
  const sorted = [...sessions].sort((a, b) => a.slot - b.slot);

  if (sorted.length === 0) {
    return <p className="text-sm text-muted-foreground">No sessions yet. Start one from a Config tab.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Slot</TableHead>
          <TableHead>Alias</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Host</TableHead>
          <TableHead>Kind</TableHead>
          <TableHead>Address Range</TableHead>
          <TableHead>Poll #</TableHead>
          <TableHead>Started</TableHead>
          <TableHead></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((session) => {
          const status = getDisplayStatus(session);
          return (
            <TableRow key={session.sessionId}>
              <TableCell>Slot {session.slot}</TableCell>
              <TableCell>{aliasBySlot[session.slot] || '—'}</TableCell>
              <TableCell><Badge variant="outline" className={status.className}>{status.label}</Badge></TableCell>
              <TableCell>{session.host}:{session.port}</TableCell>
              <TableCell>{session.kind}</TableCell>
              <TableCell>{session.start_address}–{session.end_address}</TableCell>
              <TableCell>{session.pollCount}</TableCell>
              <TableCell>{session.startedAt ? new Date(session.startedAt).toLocaleTimeString() : '—'}</TableCell>
              <TableCell>
                <Button variant="outline" size="sm" onClick={() => onSelect(session.sessionId)}>View</Button>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
