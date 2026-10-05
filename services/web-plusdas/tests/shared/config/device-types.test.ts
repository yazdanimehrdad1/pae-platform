import { describe, expect, it } from 'vitest';
import type { DeviceType } from '@/api/types/devices';
import { deviceTypeConfig } from '@/shared/config/device-types';

// Every type backend-ot accepts (DeviceCreateRequest.type in the contract). Typed against the
// contract, so this list can't silently miss one either.
const BACKEND_TYPES: Record<DeviceType, true> = {
  BESS: true, ES: true, INVERTER: true, PV: true, GENERATOR: true,
  LOADBANK: true, RELAY: true, IED: true, METER: true, RTAC: true,
};

describe('deviceTypeConfig', () => {
  it('styles every backend-ot device type (a missing one crashed the Site Devices page)', () => {
    for (const type of Object.keys(BACKEND_TYPES)) {
      const config = deviceTypeConfig[type.toLowerCase() as keyof typeof deviceTypeConfig];
      expect(config, type).toBeDefined();
      expect(config.icon, type).toBeDefined();
      expect(config.label, type).not.toBe('');
    }
  });
});
