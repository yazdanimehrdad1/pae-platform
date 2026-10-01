import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { sitesApi } from "@/api";
import { getErrorMessage } from "@/api/client";
import { MAX_ENABLED_ALARMS, type AlarmDefinitionCreateRequest, type AlarmDefinitionUpdateRequest } from "@/api/types/alarms";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "@/shared/hooks/use-toast";
import { AlarmTable } from "./components/AlarmTable";
import { DeviceDetail } from "./components/DeviceDetail";
import { DeviceList } from "./components/DeviceList";
import { HistoryDrawer } from "./components/HistoryDrawer";
import { RuleBuilder } from "./components/RuleBuilder";
import { RuleManager } from "./components/RuleManager";
import { SummaryBar } from "./components/SummaryBar";
import type { TrendRange } from "./lib/trendRange";
import { useAlarmSnapshot, useRuleMutations } from "./hooks/useAlarmsData";
import { buildAlarmModel, watchedPointId, type AlarmModel, type AlarmView } from "./lib/alarmModel";
import type { Rule } from "./types";

// backend-ot has no site time zone yet, so times show in the browser's zone.
const TIME_ZONE = Intl.DateTimeFormat().resolvedOptions().timeZone;

/**
 * The point a device's trend opens on: its alarming point, else one with a rule, else the first
 * numeric one with a value (standardized points may have no readings), else the first numeric one.
 */
function defaultPointId(model: AlarmModel, rules: Rule[], deviceId: string): string | null {
  const numeric = [...model.pointsById.values()].filter(point => point.deviceId === deviceId && point.kind === "numeric");
  const alarming = model.active.find(alarm => alarm.point?.deviceId === deviceId && alarm.point.kind === "numeric")?.point;
  const withRule = numeric.find(point => rules.some(rule => watchedPointId(rule) === point.id));
  const withValue = numeric.find(point => point.value !== null);
  return alarming?.id ?? withRule?.id ?? withValue?.id ?? numeric[0]?.id ?? null;
}

export default function AlarmsPage() {
  const { data: sites = [], isLoading: areSitesLoading } = useQuery({ queryKey: ["sites"], queryFn: sitesApi.getAll });
  const [siteId, setSiteId] = useState("");
  useEffect(() => {
    if (!siteId && sites.length > 0) setSiteId(sites[0].id);
  }, [sites, siteId]);
  const site = sites.find(candidate => candidate.id === siteId);

  return (
    <div className="h-screen overflow-y-auto">
      <div className="space-y-4 p-6">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <h1 className="text-2xl font-semibold">System alarms</h1>
          <div className="flex items-end gap-3">
            <p className="pb-2 text-sm text-muted-foreground">Times in {TIME_ZONE}</p>
            <div className="w-56 space-y-1">
              <Label htmlFor="alarms-site" className="text-xs text-muted-foreground">Site</Label>
              <Select value={siteId} onValueChange={setSiteId}>
                <SelectTrigger id="alarms-site" className="h-8 text-sm"><SelectValue placeholder="Choose a site" /></SelectTrigger>
                <SelectContent>{sites.map(option => <SelectItem key={option.id} value={option.id}>{option.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
        </header>
        {site ? (
          <SiteAlarms key={site.id} siteId={site.id} />
        ) : (
          <p className="text-sm text-muted-foreground">{areSitesLoading ? "Loading sites..." : "No sites yet."}</p>
        )}
      </div>
    </div>
  );
}

/** One site's alarms. Keyed by site, so selections reset when the site changes. */
function SiteAlarms({ siteId }: { siteId: string }) {
  const { data: snapshot, isLoading, error } = useAlarmSnapshot(siteId);
  const model = useMemo(() => (snapshot ? buildAlarmModel(snapshot) : null), [snapshot]);
  const { create, update, remove } = useRuleMutations(siteId);

  const [chosenDeviceId, setChosenDeviceId] = useState<string | null>(null);
  const [chosenPointId, setChosenPointId] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [trendRange, setTrendRange] = useState<TrendRange>("6h");
  const [isBuilderOpen, setIsBuilderOpen] = useState(false);
  // The user rule open in the builder; null for a new rule.
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [isRulesOpen, setIsRulesOpen] = useState(false);
  const [history, setHistory] = useState<{ open: boolean; deviceId: string | null; key: number }>({ open: false, deviceId: null, key: 0 });

  if (isLoading || !snapshot || !model) {
    return (
      <div className="text-sm text-muted-foreground">
        {error ? `Failed to load alarms: ${getErrorMessage(error)}` : "Loading alarms..."}
      </div>
    );
  }

  const { now, rules, devices, log } = snapshot;
  const selectedDevice = model.devicesById.get(chosenDeviceId ?? "") ?? model.sortedDevices[0] ?? null;
  const selectedPointId = selectedDevice
    ? (chosenPointId && model.pointsById.get(chosenPointId)?.deviceId === selectedDevice.id ? chosenPointId : defaultPointId(model, rules, selectedDevice.id))
    : null;
  const faults = model.active.filter(alarm => alarm.event.severity === "fault").length;
  const normalDevices = devices.filter(device => model.deviceStatus.get(device.id) === "normal").length;
  const canEnableMore = rules.filter(rule => rule.enabled).length < MAX_ENABLED_ALARMS;

  const selectDevice = (deviceId: string) => {
    setChosenDeviceId(deviceId);
    setChosenPointId(null);
  };
  const selectAlarm = (alarm: AlarmView) => {
    setSelectedEventId(alarm.event.id);
    if (!alarm.device) return; // site-level alarms have no single device to show
    setChosenDeviceId(alarm.device.id);
    setChosenPointId(alarm.point?.kind === "numeric" ? alarm.point.id : null);
  };
  // A change from the alarm table or the rules dialog: enabled, or the notification channels.
  const onChangeRule = (rule: Rule, patch: AlarmDefinitionUpdateRequest) =>
    update.mutate({ rule, patch }, {
      onError: err => toast({ title: "Updating the rule failed", description: getErrorMessage(err), variant: "destructive" }),
    });
  const onDeleteRule = (rule: Rule) =>
    remove.mutate(rule, {
      onSuccess: () => toast({ title: "Rule deleted", description: `${rule.name} and its alarm history were removed.` }),
      onError: err => toast({ title: "Deleting the rule failed", description: getErrorMessage(err), variant: "destructive" }),
    });
  const onTurnOffAllNotifications = async (notifyingRules: Rule[]) => {
    const results = await Promise.allSettled(
      notifyingRules.map(rule => update.mutateAsync({ rule, patch: { notify_mobile: false, notify_email: false } })),
    );
    const failed = results.filter(result => result.status === "rejected").length;
    if (failed === 0) {
      toast({ title: "Notifications turned off", description: `${notifyingRules.length} rules no longer notify.` });
    } else {
      toast({ title: "Some rules were not updated", description: `${failed} of ${notifyingRules.length} failed.`, variant: "destructive" });
    }
  };
  const onSaveRule = async (request: AlarmDefinitionCreateRequest) => {
    try {
      if (editingRule) {
        await update.mutateAsync({ rule: editingRule, patch: request });
        toast({ title: "Rule updated", description: request.name });
      } else {
        await create.mutateAsync(request);
        toast({ title: "Rule saved", description: `${request.name} is evaluated from the next poll.` });
      }
      setIsBuilderOpen(false);
      setEditingRule(null);
    } catch (err) {
      toast({ title: "Saving the rule failed", description: getErrorMessage(err), variant: "destructive" });
    }
  };
  const openBuilder = (rule: Rule | null) => {
    setEditingRule(rule);
    setIsBuilderOpen(true);
    setIsRulesOpen(false);
    requestAnimationFrame(() => document.getElementById("rule-builder-heading")?.scrollIntoView?.({ behavior: "smooth", block: "start" }));
  };
  const closeBuilder = () => {
    setIsBuilderOpen(false);
    setEditingRule(null);
  };
  const openHistory = (deviceId: string | null) => setHistory(prev => ({ open: true, deviceId, key: prev.key + 1 }));
  const lastClearedAt = model.recentlyCleared[0]?.event.clearedAt ?? null;

  return (
    <>
      <SummaryBar
        faults={faults}
        warnings={model.active.length - faults}
        normalDevices={normalDevices}
        totalDevices={devices.length}
        ruleCount={rules.length}
        isBuilderOpen={isBuilderOpen && !editingRule}
        onOpenRules={() => setIsRulesOpen(true)}
        onToggleBuilder={() => (isBuilderOpen && !editingRule ? closeBuilder() : openBuilder(null))}
      />

      {isBuilderOpen && (
        <RuleBuilder key={editingRule?.id ?? "new"} initial={editingRule ?? undefined}
          points={snapshot.points} devices={devices} existingNames={rules.map(rule => rule.name)}
          canEnable={canEnableMore} onSave={onSaveRule} onCancel={closeBuilder} />
      )}

      <AlarmTable
        alarms={model.active}
        model={model}
        now={now}
        timeZone={TIME_ZONE}
        selectedEventId={selectedEventId}
        lastClearedAt={lastClearedAt}
        clearedCount={model.recentlyCleared.length}
        onSelect={selectAlarm}
        onChangeNotify={(rule, notify) => onChangeRule(rule, { notify_mobile: notify.mobile, notify_email: notify.email })}
        onOpenHistory={() => openHistory(null)}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <DeviceList
          devices={model.sortedDevices}
          deviceStatus={model.deviceStatus}
          devicesWithRecentEvents={model.devicesWithRecentEvents}
          selectedDeviceId={selectedDevice?.id ?? null}
          onSelect={selectDevice}
        />
        {selectedDevice ? (
          <DeviceDetail
            siteId={siteId}
            device={selectedDevice}
            status={model.deviceStatus.get(selectedDevice.id) ?? "normal"}
            model={model}
            rules={rules}
            log={log}
            now={now}
            timeZone={TIME_ZONE}
            selectedPointId={selectedPointId}
            trendRange={trendRange}
            onTrendRangeChange={setTrendRange}
          />
        ) : (
          <p className="text-sm text-muted-foreground">This site has no devices.</p>
        )}
      </div>

      <RuleManager
        open={isRulesOpen}
        onOpenChange={setIsRulesOpen}
        rules={rules}
        model={model}
        timeZone={TIME_ZONE}
        onChange={onChangeRule}
        onEdit={openBuilder}
        onDelete={onDeleteRule}
        onTurnOffAllNotifications={onTurnOffAllNotifications}
      />
      <HistoryDrawer
        key={history.key}
        siteId={siteId}
        open={history.open}
        onOpenChange={open => setHistory(prev => ({ ...prev, open }))}
        model={model}
        devices={model.sortedDevices}
        now={now}
        timeZone={TIME_ZONE}
        initialDeviceId={history.deviceId}
      />
    </>
  );
}
