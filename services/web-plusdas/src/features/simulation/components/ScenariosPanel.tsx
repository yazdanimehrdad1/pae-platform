import type { ConditionsReport, SiteConfig } from "@/api/types/powerflow";
import { AutoDispatchCard } from "./scenarios/AutoDispatchCard";
import { BatteryCard } from "./scenarios/BatteryCard";
import { EventScenarioList } from "./scenarios/EventScenarioList";
import { LiveConditions } from "./scenarios/LiveConditions";

interface Props {
  siteName: string;
  config: SiteConfig;
  isActive: boolean;
  report: ConditionsReport | undefined;
}

// Scenarios: inject conditions (breakers, faults, comm loss, grid events) into the simulation,
// live or as a stored, timed event scenario of the selected site, auto dispatch the BESS and
// override their batteries (SOC, efficiency).
export function ScenariosPanel({ siteName, config, isActive, report }: Props) {
  return (
    <div className="space-y-4">
      <AutoDispatchCard config={config} enabled={isActive} />
      <BatteryCard config={config} enabled={isActive} />
      <LiveConditions config={config} report={isActive ? report : undefined} enabled={isActive} />
      <EventScenarioList siteName={siteName} config={config} isActive={isActive} report={isActive ? report : undefined} />
    </div>
  );
}
