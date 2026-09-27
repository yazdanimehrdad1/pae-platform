// Health board mocks. backend-ot has only a live health snapshot, no history or test results
// (docs/backend-gaps.md, "Health timeline").
import type { HealthState, SystemTestResult } from '@/features/health/types';

export const MOCK_HEALTH_DEVICE_NAMES = [
  "Transformer T1", "Transformer T2", "Generator G1", "Feeder F1",
  "Protection P1", "Protection P2", "Switch S1", "Switch S2",
];

// 48 h of hourly random states per device: about 5% down, 15% warning, the rest OK.
export function generateMockHealthHistory(deviceIds: string[]): HealthState[] {
  const now = Date.now();
  const states: HealthState[] = [];

  deviceIds.forEach(deviceId => {
    for (let i = 48; i >= 0; i--) {
      const timestamp = now - (i * 3600000);
      let state: 0 | 1 | 2 = 2;

      if (Math.random() < 0.05) state = 0;
      else if (Math.random() < 0.15) state = 1;

      states.push({
        timestamp,
        deviceId,
        state,
        message: state === 0 ? 'Communication Lost' :
          state === 1 ? 'High Temperature' : 'Normal'
      });
    }
  });

  return states;
}

export const MOCK_PASSED_SYSTEMS: SystemTestResult[] = [
  { name: 'BESS Unit 1', test: 'Self Discharge', status: 'PASS', lastRun: 'Dec 12, 2024 14:30', reportId: 'report-1' },
  { name: 'BESS Unit 2', test: 'Self Discharge', status: 'PASS', lastRun: 'Dec 12, 2024 14:30', reportId: 'report-2' },
  { name: 'BESS Unit 3', test: 'Self Discharge', status: 'PASS', lastRun: 'Dec 12, 2024 14:30', reportId: 'report-3' },
  { name: 'Transformer T1', test: 'Thermal Performance', status: 'PASS', lastRun: 'Dec 11, 2024 16:45', reportId: 'report-4' },
  { name: 'Transformer T2', test: 'Thermal Performance', status: 'PASS', lastRun: 'Dec 11, 2024 16:45', reportId: 'report-5' },
];
