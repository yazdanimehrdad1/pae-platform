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
export type ModbusSessionsResponse = Schemas['LiveStreamSessionsResponse'];

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
