import type { components } from '@contracts/backend-ot';

type Schemas = components['schemas'];
type StreamParams = Schemas['LiveStreamRawRegistersParams'];

// Wire types: generated from backend-ot's contract, never hand-written.
export type ModbusRegisterKind = StreamParams['kind'];
export type ModbusAddressMode = StreamParams['modbus_address_mode'];
export type ModbusByteOrder = StreamParams['byte_order'];
export type ModbusWordOrder = StreamParams['word_order'];
export type ModbusRegisterConfig = Schemas['LiveStreamRawRegistersRegisterConfig'];
export type ModbusLiveStreamRequest = StreamParams;
export type ModbusSessionSummary = Schemas['LiveStreamSessionInfo'];

// Server-sent event payloads of the stream. The OpenAPI contract does not describe SSE
// bodies, so these stay hand-written (see docs/backend-gaps.md).
export interface ModbusConnectedEvent {
  session_id: string;
}

export interface ModbusPolledRegister {
  value: number;
  label: string;
  data_type: string;
}

export interface ModbusPollEvent {
  timestamp: string;
  poll: number;
  registers: Record<string, ModbusPolledRegister>;
}

export interface ModbusDoneEvent {
  total_polls: number;
  duration_s: number;
}

// UI state for one attached stream (not a wire type).
export type ModbusAttachment = 'idle' | 'connecting' | 'streaming' | 'error';

export interface ModbusSessionState {
  sessionId: string;
  slot: number;
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
