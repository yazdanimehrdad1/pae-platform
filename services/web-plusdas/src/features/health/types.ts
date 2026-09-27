// Health of one device at one hour: 0 = down, 1 = warning, 2 = OK.
export interface HealthState {
  timestamp: number;
  deviceId: string;
  state: 0 | 1 | 2;
  message?: string;
}

export interface SystemTestResult {
  name: string;
  test: string;
  status: 'PASS' | 'FAIL';
  lastRun: string;
  reportId: string;
}
