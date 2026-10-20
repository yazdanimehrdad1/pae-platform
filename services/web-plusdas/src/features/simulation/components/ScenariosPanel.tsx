import type { ConditionsReport, SiteConfig } from "@/api/types/powerflow";
import { AutoDispatchCard } from "./scenarios/AutoDispatchCard";
import { EventScenarioList } from "./scenarios/EventScenarioList";
import { LiveConditions } from "./scenarios/LiveConditions";

interface Props {
  siteName: string;
  config: SiteConfig;
  isActive: boolean;
  report: ConditionsReport | undefined;
}

// Scenarios: inject conditions (breakers, faults, comm loss, grid events) into the simulation,
// live or as a stored, timed event scenario of the selected site, and auto dispatch the BESS.
export function ScenariosPanel({ siteName, config, isActive, report }: Props) {
  return (
    <div className="space-y-4">
      <AutoDispatchCard config={config} enabled={isActive} />
      <LiveConditions config={config} report={isActive ? report : undefined} enabled={isActive} />
      <EventScenarioList siteName={siteName} config={config} isActive={isActive} report={isActive ? report : undefined} />
    </div>
  );
}
