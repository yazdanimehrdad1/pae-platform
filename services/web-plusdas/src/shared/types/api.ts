export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
  timestamp: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
}

export interface TimeSeriesRequest {
  siteId: string;
  deviceId: string;
  points: string[];
  from: number;
  to: number;
  interval?: 'raw' | '1m' | '5m' | '15m' | '1h' | '1d';
}

export interface TimeSeriesPoint {
  timestamp: number;
  value: number;
  quality?: 'good' | 'bad' | 'uncertain';
}

export interface TimeSeriesResponse {
  point: string;
  data: TimeSeriesPoint[];
  unit?: string;
}

export type TimeRange = '1H' | '6H' | '12H' | '1D' | '2D' | '3D' | '1W' | '1M' | '3M';

interface DevicePointReadingsBase {
  siteId: string;
  deviceId: string;
  pointIds: string[];
}
export type DevicePointReadingsRequest =
  | (DevicePointReadingsBase & { timeRange: TimeRange })
  | (DevicePointReadingsBase & { startTime: string; endTime: string });

export interface BackendPointReadings {
  meta: {
    site_id: number;
    device_id: number;
    point_ids: number[];
    total_count: number;
    start_time?: string;
    end_time?: string;
  };
  readings: Record<string, {
    id: number;
    name: string;
    data_type: string;
    unit?: string;
    count: number;
    timeseries: Array<{ time: string; value?: number | null }>;
  }>;
}

export interface HealthStateResponse {
  deviceId: string;
  state: 0 | 1 | 2;
  message?: string;
  timestamp: string;
}

export interface SiteListResponse {
  sites: Array<{
    id: string;
    name: string;
    location: string;
    status: string;
    deviceCount: number;
    lastUpdate: string;
  }>;
}
