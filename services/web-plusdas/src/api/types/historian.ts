import type { components, paths } from '@contracts/backend-ot';

// Wire types: generated from backend-ot's contract, never hand-written.
type TimeseriesQuery = NonNullable<
  paths['/api/device-point-readings/timeseries/site/{site_id}/device/{device_id}']['get']['parameters']['query']
>;
export type TimeRange = NonNullable<TimeseriesQuery['time_range']>;
export type BackendPointReadings = components['schemas']['TimeseriesResponse'];
export type LatestPointReadings = components['schemas']['LatestResponse'];
export type PointTimeseries = components['schemas']['PointTimeseries'];

// Arguments of historianApi.getDevicePointReadings (a client call signature, not a wire type).
interface DevicePointReadingsBase {
  siteId: string;
  deviceId: string;
  pointIds: string[];
  // A chart's request: every reading up to 3 days, plot values beyond, with gap markers (no value).
  maxPoints?: number;
}
export type DevicePointReadingsRequest =
  | (DevicePointReadingsBase & { timeRange: TimeRange })
  | (DevicePointReadingsBase & { startTime: string; endTime: string });
