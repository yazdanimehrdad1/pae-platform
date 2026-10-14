import type { components } from '@contracts/backend-ot';
import type { PointTimeseries, TimeRange } from './historian';

type Schemas = components['schemas'];

// Wire types: generated from backend-ot's contract, never hand-written.
export type SiteEndpointsResponse = Schemas['SiteEndpointsResponse'];
export type SiteEndpointInfo = Schemas['SiteEndpointInfo'];

// What every endpoint with output "series" returns, whatever its other fields: backend-ot's
// profile registry requires `series` to be one PointTimeseries or a list of them.
export interface SeriesFunctionResponse {
  series: PointTimeseries | PointTimeseries[];
}

// Arguments of siteFunctionsApi.getSeries (a client call signature, not a wire type).
// `deviceId` is set for a device function and omitted for a site or common one.
interface FunctionSeriesBase {
  siteId: string;
  name: string;
  deviceId?: string;
  // A chart's request, as for the readings endpoint: the returned series are sampled.
  maxPoints?: number;
}
export type FunctionSeriesRequest =
  | (FunctionSeriesBase & { timeRange: TimeRange })
  | (FunctionSeriesBase & { startTime: string; endTime: string });
