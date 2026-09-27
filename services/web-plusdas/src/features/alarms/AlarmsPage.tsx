import { useMemo, useState } from "react";
import { getErrorMessage } from "@/api/client";
import { toast } from "@/shared/hooks/use-toast";
import { AlarmTable } from "./components/AlarmTable";
import { DeviceDetail } from "./components/DeviceDetail";
import { DeviceList } from "./components/DeviceList";
import { HistoryDrawer } from "./components/HistoryDrawer";
import { RuleBuilder } from "./components/RuleBuilder";
import { RuleManager } from "./components/RuleManager";
import { SummaryBar } from "./components/SummaryBar";
import type { TrendRange } from "./lib/trendRange";
import { useAlarmSnapshot, useSaveRule } from "./hooks/useAlarmsData";
import { buildAlarmModel, type AlarmModel, type AlarmView } from "./lib/alarmModel";
import type { Rule } from "./types";

/** The point a device's trend opens on: its alarming point, else one with a rule, else the first numeric one. */
function defaultPointId(model: AlarmModel, rules: Rule[], deviceId: string): string | null {
  const numeric = [...model.pointsById.values()].filter(point => point.deviceId === deviceId && point.kind === "numeric");
  const alarming = model.active.find(alarm => alarm.point?.deviceId === deviceId && alarm.point.kind === "numeric")?.point;
  const withRule = numeric.find(point => rules.some(rule => rule.type === "threshold" && rule.pointId === point.id));
  return alarming?.id ?? withRule?.id ?? numeric[0]?.id ?? null;
}

export default function AlarmsPage() {
  const { data: snapshot, isLoading, error } = useAlarmSnapshot();
  const model = useMemo(() => (snapshot ? buildAlarmModel(snapshot) : null), [snapshot]);
  const saveRule = useSaveRule();

  const [chosenDeviceId, setChosenDeviceId] = useState<string | null>(null);
  const [chosenPointId, setChosenPointId] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [trendRange, setTrendRange] = useState<TrendRange>("6h");
  const [isBuilderOpen, setIsBuilderOpen] = useState(false);
  const [isRulesOpen, setIsRulesOpen] = useState(false);
  const [history, setHistory] = useState<{ open: boolean; deviceId: string | null; key: number }>({ open: false, deviceId: null, key: 0 });

  if (isLoading || !snapshot || !model) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        {error ? `Failed to load alarms: ${getErrorMessage(error)}` : "Loading alarms..."}
      </div>
    );
  }

  const { site, now, rules, devices, log } = snapshot;
  const selectedDevice = model.devicesById.get(chosenDeviceId ?? "") ?? model.sortedDevices[0] ?? null;
  const selectedPointId = selectedDevice
    ? (chosenPointId && model.pointsById.get(chosenPointId)?.deviceId === selectedDevice.id ? chosenPointId : defaultPointId(model, rules, selectedDevice.id))
    : null;
  const faults = model.active.filter(alarm => alarm.event.severity === "fault").length;
  const normalDevices = devices.filter(device => model.deviceStatus.get(device.id) === "normal").length;

  const selectDevice = (deviceId: string) => {
    setChosenDeviceId(deviceId);
    setChosenPointId(null);
  };
  const selectAlarm = (alarm: AlarmView) => {
    setSelectedEventId(alarm.event.id);
    if (!alarm.device) return; // calculated (site-level) alarms have no single device to show
    setChosenDeviceId(alarm.device.id);
    setChosenPointId(alarm.point?.kind === "numeric" ? alarm.point.id : null);
  };
  // A change from the alarm table or the rules dialog: enabled, or the notification channels.
  const onChangeRule = (rule: Rule) =>
    saveRule.mutate(rule, {
      onError: err => toast({ title: "Updating the rule failed", description: getErrorMessage(err), variant: "destructive" }),
    });
  const onTurnOffAllNotifications = async (notifyingRules: Rule[]) => {
    const results = await Promise.allSettled(
      notifyingRules.map(rule => saveRule.mutateAsync({ ...rule, notify: { mobile: false, email: false } })),
    );
    const failed = results.filter(result => result.status === "rejected").length;
    if (failed === 0) {
      toast({ title: "Notifications turned off", description: `${notifyingRules.length} rules no longer notify.` });
    } else {
      toast({ title: "Some rules were not updated", description: `${failed} of ${notifyingRules.length} failed.`, variant: "destructive" });
    }
  };
  const onSaveRule = async (rule: Rule) => {
    try {
      await saveRule.mutateAsync(rule);
      setIsBuilderOpen(false);
      toast({ title: "Rule saved", description: rule.name });
    } catch (err) {
      toast({ title: "Saving the rule failed", description: getErrorMessage(err), variant: "destructive" });
    }
  };
  const openHistory = (deviceId: string | null) => setHistory(prev => ({ open: true, deviceId, key: prev.key + 1 }));
  const lastClearedAt = model.recentlyCleared[0]?.event.clearedAt ?? null;

  return (
    <div className="h-screen overflow-y-auto">
      <div className="space-y-4 p-6">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-2xl font-semibold">System alarms</h1>
          <p className="text-sm text-muted-foreground">{site.name} · times in {site.timeZone}</p>
        </header>

        <SummaryBar
          faults={faults}
          warnings={model.active.length - faults}
          normalDevices={normalDevices}
          totalDevices={devices.length}
          ruleCount={rules.length}
          isBuilderOpen={isBuilderOpen}
          onOpenRules={() => setIsRulesOpen(true)}
          onToggleBuilder={() => setIsBuilderOpen(open => !open)}
        />

        {isBuilderOpen && (
          <RuleBuilder devices={devices} points={snapshot.points} existingNames={rules.map(rule => rule.name)}
            defaultPointId={selectedPointId}
            onSave={onSaveRule} onCancel={() => setIsBuilderOpen(false)} />
        )}

        <AlarmTable
          alarms={model.active}
          now={now}
          timeZone={site.timeZone}
          selectedEventId={selectedEventId}
          lastClearedAt={lastClearedAt}
          clearedCount={model.recentlyCleared.length}
          onSelect={selectAlarm}
          onChangeNotify={(rule, notify) => onChangeRule({ ...rule, notify })}
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
          {selectedDevice && (
            <DeviceDetail
              device={selectedDevice}
              status={model.deviceStatus.get(selectedDevice.id) ?? "normal"}
              model={model}
              rules={rules}
              log={log}
              now={now}
              timeZone={site.timeZone}
              selectedPointId={selectedPointId}
              trendRange={trendRange}
              onSelectPoint={setChosenPointId}
              onTrendRangeChange={setTrendRange}
              onOpenHistory={() => openHistory(selectedDevice.id)}
            />
          )}
        </div>
      </div>

      <RuleManager
        open={isRulesOpen}
        onOpenChange={setIsRulesOpen}
        rules={rules}
        devicesById={model.devicesById}
        pointsById={model.pointsById}
        onChange={onChangeRule}
        onTurnOffAllNotifications={onTurnOffAllNotifications}
      />
      <HistoryDrawer
        key={history.key}
        open={history.open}
        onOpenChange={open => setHistory(prev => ({ ...prev, open }))}
        model={model}
        devices={model.sortedDevices}
        now={now}
        timeZone={site.timeZone}
        initialDeviceId={history.deviceId}
      />
    </div>
  );
}
