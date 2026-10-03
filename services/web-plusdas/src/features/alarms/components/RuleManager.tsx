import { useState } from "react";
import { BellOff, Pencil, Trash2 } from "lucide-react";
import type { AlarmDefinitionUpdateRequest } from "@/api/types/alarms";
import { MAX_ENABLED_ALARMS } from "@/api/types/alarms";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { describeCondition, KIND_LABEL, ruleDeviceId, type AlarmModel } from "../lib/alarmModel";
import { formatSiteTime } from "../lib/siteTime";
import type { Rule } from "../types";
import { NotificationToggles } from "./NotificationToggles";
import { SeverityIndicator } from "./SeverityIndicator";

/** Delay, deadband or timeout of a rule, as short lines. */
function ruleSettings(rule: Rule): string[] {
  const spec = rule.rule;
  if (!spec) return ["Logic in the site profile"];
  if (spec.kind === "comms_stale") return [`Timeout ${spec.stale_after_sec} s`];
  const settings = [`Delay ${spec.delay_sec} s`];
  if (spec.kind === "threshold" && spec.deadband > 0) settings.push(`Deadband ${spec.deadband}`);
  return settings;
}

/**
 * Every alarm of the site, user rules and site-profile alarms, with everything about each: what it
 * checks, where, its settings and message, when it changed; its switches (notifications, enabled =
 * evaluated and shown in Active alarms), and Edit and Delete for user rules. Profile alarms are
 * defined in code: only their switches change, and they show no Edit or Delete.
 */
export function RuleManager({ open, onOpenChange, rules, model, timeZone, onChange, onEdit, onDelete, onTurnOffAllNotifications }: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  rules: Rule[];
  model: AlarmModel;
  timeZone: string;
  /** Saves the changed fields of a rule. */
  onChange: (rule: Rule, patch: AlarmDefinitionUpdateRequest) => void;
  /** Opens a user rule in the rule builder. */
  onEdit: (rule: Rule) => void;
  /** Permanently deletes a user rule and its alarm history. */
  onDelete: (rule: Rule) => void;
  /** Turns mobile and email off on every rule that has either on. */
  onTurnOffAllNotifications: (rules: Rule[]) => void;
}) {
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [ruleToDelete, setRuleToDelete] = useState<Rule | null>(null);
  const notifyingRules = rules.filter(rule => rule.notify.mobile || rule.notify.email);
  const enabledCount = rules.filter(rule => rule.enabled).length;
  const isEnabledFull = enabledCount >= MAX_ENABLED_ALARMS;
  const deviceName = (rule: Rule) => {
    const deviceId = ruleDeviceId(rule, model.pointsById);
    return deviceId ? model.devicesById.get(deviceId)?.name ?? `Device ${deviceId}` : "Site";
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-7xl">
        <DialogHeader>
          <div className="flex flex-wrap items-start justify-between gap-3 pr-8">
            <DialogTitle>Alarm rules ({rules.length})</DialogTitle>
            <Button variant="outline" size="sm" className="gap-1" disabled={notifyingRules.length === 0}
              onClick={() => setIsConfirmOpen(true)}>
              <BellOff className="h-4 w-4" />Turn off all notifications
            </Button>
          </div>
          <DialogDescription>
            An enabled rule is evaluated and its alarms show in Active alarms; up to {MAX_ENABLED_ALARMS} rules can be
            enabled ({enabledCount} of {MAX_ENABLED_ALARMS} now). A disabled rule raises no alarms and clears its active one.
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

        <AlertDialog open={ruleToDelete !== null} onOpenChange={isOpen => { if (!isOpen) setRuleToDelete(null); }}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete {ruleToDelete?.name}?</AlertDialogTitle>
              <AlertDialogDescription>
                The rule and its whole alarm history (every raise and clear) are removed permanently. This can't be undone.
                To stop it without losing its history, disable it instead.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                onClick={() => { if (ruleToDelete) onDelete(ruleToDelete); setRuleToDelete(null); }}
              >
                Delete permanently
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        <div className="max-h-[65vh] overflow-y-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Severity</TableHead>
                <TableHead>Rule</TableHead>
                <TableHead>Condition</TableHead>
                <TableHead>Device</TableHead>
                <TableHead>Settings</TableHead>
                <TableHead className="w-44">Notifications</TableHead>
                <TableHead className="w-16">Enabled</TableHead>
                <TableHead className="w-20"><span className="sr-only">Edit or delete</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.map(rule => {
                const isProfile = rule.source === "PROFILE";
                const cannotEnable = !rule.enabled && isEnabledFull;
                return (
                  <TableRow key={rule.id} className="align-top">
                    <TableCell><SeverityIndicator severity={rule.severity} /></TableCell>
                    <TableCell>
                      <div className="font-mono text-xs">{rule.name}</div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        <Badge variant={isProfile ? "secondary" : "outline"} className="text-[10px]">
                          {isProfile ? "Site profile" : "User"}
                        </Badge>
                        {!isProfile && <Badge variant="outline" className="text-[10px]">{KIND_LABEL[rule.kind]}</Badge>}
                      </div>
                    </TableCell>
                    <TableCell className="max-w-sm">
                      <div>{describeCondition(rule, model.pointsById, model.devicesById)}</div>
                      {rule.message && rule.rule && <div className="mt-1 text-xs text-muted-foreground">Message: {rule.message}</div>}
                      {isProfile && rule.profileKey && <div className="mt-1 font-mono text-xs text-muted-foreground">{rule.profileKey}</div>}
                    </TableCell>
                    <TableCell>{deviceName(rule)}</TableCell>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                      {ruleSettings(rule).map(setting => <div key={setting}>{setting}</div>)}
                      <div title={`Created ${formatSiteTime(rule.createdAt, timeZone, { withDate: true })}`}>
                        Updated {formatSiteTime(rule.updatedAt, timeZone, { withDate: true })}
                      </div>
                    </TableCell>
                    <TableCell>
                      <NotificationToggles value={rule.notify}
                        onChange={notify => onChange(rule, { notify_mobile: notify.mobile, notify_email: notify.email })}
                        label={`Notifications for ${rule.name}`} />
                    </TableCell>
                    <TableCell>
                      <Switch checked={rule.enabled} disabled={cannotEnable} onCheckedChange={enabled => onChange(rule, { enabled })}
                        title={cannotEnable ? `${MAX_ENABLED_ALARMS} rules are already enabled; disable one first` : undefined}
                        aria-label={`${rule.enabled ? "Disable" : "Enable"} ${rule.name}`} />
                    </TableCell>
                    <TableCell>
                      {!isProfile && (
                        <div className="flex">
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground"
                            aria-label={`Edit ${rule.name}`} onClick={() => onEdit(rule)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-destructive"
                            aria-label={`Delete ${rule.name}`} onClick={() => setRuleToDelete(rule)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      )}
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
