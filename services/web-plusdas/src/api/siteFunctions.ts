import type { PointTimeseries } from './types/historian';
import type {
  FunctionSeriesRequest,
  SeriesFunctionResponse,
  SiteEndpointsResponse,
} from './types/siteFunctions';
import { client } from './client';

export const siteFunctionsApi = {
  /** The functions the site's profile declares (none when the site has no profile). */
  list: (siteId: string): Promise<SiteEndpointsResponse> =>
    client.get(`/site-functions/site/${siteId}`),

  /** Runs a series function over a window; one series or a list, always returned as a list. */
  getSeries: async (req: FunctionSeriesRequest): Promise<PointTimeseries[]> => {
    const params = new URLSearchParams();
    if (req.maxPoints !== undefined) params.set('max_points', String(req.maxPoints));
    if ('timeRange' in req) {
      params.set('time_range', req.timeRange);
    } else {
      params.set('start_time', req.startTime);
      params.set('end_time', req.endTime);
    }
    const path = req.deviceId
      ? `/site-functions/site/${req.siteId}/device/${req.deviceId}/${req.name}`
      : `/site-functions/site/${req.siteId}/${req.name}`;
    const response = await client.get<SeriesFunctionResponse>(`${path}?${params}`);
    return Array.isArray(response.series) ? response.series : [response.series];
  },
};
