import type { components, paths } from '@contracts/backend-ot';

// Client-side error shape: FastAPI's JSON error body (with `detail`), or this fallback when the
// body isn't JSON (src/api/client.ts).
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

// Wire types: generated from backend-ot's contract, never hand-written.
type TimeseriesQuery = NonNullable<
  paths['/api/device-point-readings/timeseries/site/{site_id}/device/{device_id}']['get']['parameters']['query']
>;
export type TimeRange = NonNullable<TimeseriesQuery['time_range']>;
export type BackendPointReadings = components['schemas']['TimeseriesResponse'];

// Arguments of historianApi.getDevicePointReadings (a client call signature, not a wire type).
interface DevicePointReadingsBase {
  siteId: string;
  deviceId: string;
  pointIds: string[];
}
export type DevicePointReadingsRequest =
  | (DevicePointReadingsBase & { timeRange: TimeRange })
  | (DevicePointReadingsBase & { startTime: string; endTime: string });
