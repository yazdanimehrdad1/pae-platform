export type ModbusRegisterKind = 'holding' | 'input' | 'coils';
export type ModbusAddressMode = 'zero_based' | 'one_based';
export type ModbusByteOrder = 'big' | 'little';
export type ModbusWordOrder = 'msw_first' | 'lsw_first';

export interface ModbusRegisterConfig {
  label?: string;
  data_type?: string;
  byte_order?: ModbusByteOrder;
  word_order?: ModbusWordOrder;
}

export interface ModbusLiveStreamRequest {
  host: string;
  port: number;
  server_address: number;
  kind: ModbusRegisterKind;
  start_address: number;
  end_address: number;
  modbus_address_mode: ModbusAddressMode;
  interval: number;
  duration: number;
  byte_order: ModbusByteOrder;
  word_order: ModbusWordOrder;
  register_configs: Record<string, ModbusRegisterConfig>;
}

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

export interface ModbusSessionSummary {
  session_id: string;
  status: string;
  host: string;
  port: number;
  server_address: number;
  kind: ModbusRegisterKind;
  start_address: number;
  end_address: number;
  interval: number;
  duration: number;
  modbus_address_mode: ModbusAddressMode;
}

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
