import { useState } from "react";
import { BellOff } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { describeCondition } from "../lib/alarmModel";
import type { Device, Point, Rule } from "../types";
import { NotificationToggles } from "./NotificationToggles";
import { SeverityIndicator } from "./SeverityIndicator";

/** All alarm rules, each with its notification channels and an enable switch. */
export function RuleManager({ open, onOpenChange, rules, devicesById, pointsById, onChange, onTurnOffAllNotifications }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  rules: Rule[];
  devicesById: Map<string, Device>;
  pointsById: Map<string, Point>;
  /** Saves the rule with a changed switch. */
  onChange: (rule: Rule) => void;
  /** Turns mobile and email off on every rule that has either on. */
  onTurnOffAllNotifications: (rules: Rule[]) => void;
}) {
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const notifyingRules = rules.filter(rule => rule.notify.mobile || rule.notify.email);
  const sourceOf = (rule: Rule) => {
    const deviceId = rule.type === "threshold" ? pointsById.get(rule.pointId)?.deviceId ?? null : rule.deviceId;
    return deviceId ? devicesById.get(deviceId)?.name ?? deviceId : "Site (calculated)";
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <div className="flex flex-wrap items-start justify-between gap-3 pr-8">
            <DialogTitle>Alarm rules ({rules.length})</DialogTitle>
            <Button variant="outline" size="sm" className="gap-1" disabled={notifyingRules.length === 0}
              onClick={() => setIsConfirmOpen(true)}>
              <BellOff className="h-4 w-4" />Turn off all notifications
            </Button>
          </div>
          <DialogDescription>
            A disabled rule raises no alarms and clears its active ones. When a rule raises an alarm, it notifies
            on each selected channel: mobile push, email, or both.
            {" "}{notifyingRules.length} of {rules.length} rules send notifications.
          </DialogDescription>
        </DialogHeader>
        <AlertDialog open={isConfirmOpen} onOpenChange={setIsConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Turn off all notifications?</AlertDialogTitle>
              <AlertDialogDescription>
                Mobile and email notifications will be turned off for {notifyingRules.length}{" "}
                {notifyingRules.length === 1 ? "rule" : "rules"}. Alarms still raise and show on this page. You can turn
                channels back on per rule.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={() => onTurnOffAllNotifications(notifyingRules)}>Turn off</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        <div className="max-h-[60vh] overflow-y-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Severity</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Condition</TableHead>
                <TableHead>Source</TableHead>
                <TableHead className="text-right">Deadband</TableHead>
                <TableHead className="w-44">Notifications</TableHead>
                <TableHead className="w-20">Enabled</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.map(rule => {
                const point = rule.type === "threshold" ? pointsById.get(rule.pointId) ?? null : null;
                return (
                  <TableRow key={rule.id}>
                    <TableCell><SeverityIndicator severity={rule.severity} /></TableCell>
                    <TableCell className="font-mono text-xs">{rule.name}</TableCell>
                    <TableCell>{describeCondition(rule, point)}</TableCell>
                    <TableCell>{sourceOf(rule)}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {rule.type === "threshold" ? `${rule.deadband}${point?.unit ? ` ${point.unit}` : ""}` : "—"}
                    </TableCell>
                    <TableCell>
                      <NotificationToggles value={rule.notify} onChange={notify => onChange({ ...rule, notify })}
                        label={`Notifications for ${rule.name}`} />
                    </TableCell>
                    <TableCell>
                      <Switch checked={rule.enabled} onCheckedChange={enabled => onChange({ ...rule, enabled })}
                        aria-label={`${rule.enabled ? "Disable" : "Enable"} ${rule.name}`} />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>
  );
}
