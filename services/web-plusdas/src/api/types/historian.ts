import type { components, paths } from '@contracts/backend-ot';

// Wire types: generated from backend-ot's contract, never hand-written.
type TimeseriesQuery = NonNullable<
  paths['/api/device-point-readings/timeseries/site/{site_id}/device/{device_id}']['get']['parameters']['query']
>;
export type TimeRange = NonNullable<TimeseriesQuery['time_range']>;
export type BackendPointReadings = components['schemas']['TimeseriesResponse'];
export type LatestPointReadings = components['schemas']['LatestResponse'];

// Arguments of historianApi.getDevicePointReadings (a client call signature, not a wire type).
interface DevicePointReadingsBase {
  siteId: string;
  deviceId: string;
  pointIds: string[];
}
export type DevicePointReadingsRequest =
  | (DevicePointReadingsBase & { timeRange: TimeRange })
  | (DevicePointReadingsBase & { startTime: string; endTime: string });
