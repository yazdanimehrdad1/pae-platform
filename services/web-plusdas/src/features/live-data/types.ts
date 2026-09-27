import type {
  ModbusAddressMode,
  ModbusPolledRegister,
  ModbusRegisterConfig,
  ModbusRegisterKind,
} from '@/api/types/modbusStream';

// How a session tab shows its data: every poll as it streams in, or the last polls kept by
// backend-ot (the register snapshot endpoint). Either way the session streams the same.
export type ModbusViewMode = 'live' | 'snapshot';

// UI state for one attached stream (not a wire type).
export type ModbusAttachment = 'idle' | 'connecting' | 'streaming' | 'error';

export interface ModbusSessionState {
  sessionId: string;
  slot: number;
  viewMode: ModbusViewMode;
  host: string;
  port: number;
  server_address: number;
  kind: ModbusRegisterKind;
  start_address: number;
  end_address: number;
  modbus_address_mode: ModbusAddressMode;
  interval: number;
  duration: number;
  serverStatus: string;
  attachment: ModbusAttachment;
  pollCount: number;
  lastTimestamp: string | null;
  registers: Record<string, ModbusPolledRegister>;
  registerConfigs: Record<string, ModbusRegisterConfig>;
  error: string | null;
  startedAt: string | null;
}
