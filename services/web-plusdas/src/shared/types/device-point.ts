export interface DevicePoint {
  id: number;
  site_id: number;
  device_id: number;
  name: string;
  address: number;
  size: number;
  data_type: string;
  scale_factor: number | null;
  unit: string | null;
  enum_detail: Record<string, string> | null;
  bitfield_detail: Record<string, string> | null;
  byte_order: string;
  word_order: string;
  register_offset: number;
  poll_kind: 'holding' | 'input' | 'coils' | null;
  category: 'NATIVE' | 'STANDARDIZED' | 'VIRTUAL';
  deleted_at: string | null;
}

export interface DevicePointCreateRequest {
  name: string;
  size: number;
  data_type: string;
  poll_kind?: 'holding' | 'input' | 'coils' | null;
  address?: number | null;
  scale_factor?: number | null;
  unit?: string | null;
  byte_order?: string;
  word_order?: string;
  register_offset?: number;
  bitfield_detail?: Record<string, string> | null;
  enum_detail?: Record<string, string> | null;
  category?: 'NATIVE' | 'STANDARDIZED' | 'VIRTUAL';
}

export type DevicePointUpdateRequest = Partial<Omit<DevicePointCreateRequest, 'category'>>;
