import { describe, expect, it, vi } from 'vitest';
import { forecastApi, toForecastSeries } from '@/api/forecast';
import type { PvForecastResponse } from '@/api/types/forecast';

function interval(start: string, end: string, ac: number, deviceAc: number) {
  return {
    interval_start: start, interval_end: end, pv_ac_kw: ac,
    ghi: 500, temp_air_c: 25, wind_speed_ms: 2, cloud_cover_pct: 40,
    arrays: [{ array_id: 4, pv_ac_kw: deviceAc }],
  };
}

const RESPONSE = {
  site_id: 1001, provider: 'open_meteo', source_kind: 'weather_model', fallback_used: false,
  issued_at: '2026-10-21T11:00:00Z', resolution_minutes: 15, interval_convention: '',
  units: { pv_ac_kw: 'kW', cloud_cover_pct: '%' },
  intervals: [
    interval('2026-10-21T12:00:00Z', '2026-10-21T12:15:00Z', 1000, 500),
    interval('2026-10-21T12:15:00Z', '2026-10-21T12:30:00Z', 1100, 550),
  ],
} as unknown as PvForecastResponse;

describe('forecastApi.getSeries', () => {
  it('calls the as-forecast series on the intelli-gateway origin path', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(RESPONSE), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await forecastApi.getSeries('1001', '2026-10-21T00:00:00.000Z', '2026-10-22T00:00:00.000Z');

    const url = new URL(fetchMock.mock.calls[0][0], 'http://web.test');
    expect(url.pathname).toBe('/intelli-gateway-api/v1/sites/1001/forecast/series');
    expect(url.searchParams.get('start')).toBe('2026-10-21T00:00:00.000Z');
    expect(url.searchParams.get('end')).toBe('2026-10-22T00:00:00.000Z');
  });
});

describe('toForecastSeries', () => {
  it('gives each selection its interval values, a closing sample at the last interval end, and its unit', () => {
    const series = toForecastSeries(RESPONSE, ['fc:site:pv_ac_kw', 'fc:4:pv_ac_kw', 'fc:site:cloud_cover_pct', '7', 'fn:energy']);
    expect(Object.keys(series)).toEqual(['fc:site:pv_ac_kw', 'fc:4:pv_ac_kw', 'fc:site:cloud_cover_pct']);
    expect(series['fc:site:pv_ac_kw'].timeseries).toEqual([
      { time: '2026-10-21T12:00:00Z', value: 1000 },
      { time: '2026-10-21T12:15:00Z', value: 1100 },
      { time: '2026-10-21T12:30:00Z', value: 1100 },
    ]);
    expect(series['fc:site:pv_ac_kw'].unit).toBe('kW');
    expect(series['fc:4:pv_ac_kw'].timeseries?.map(point => point.value)).toEqual([500, 550, 550]);
    expect(series['fc:4:pv_ac_kw'].unit).toBe('kW');
    expect(series['fc:site:cloud_cover_pct'].timeseries?.map(point => point.value)).toEqual([40, 40, 40]);
    expect(series['fc:site:cloud_cover_pct'].unit).toBe('%');
  });

  it('has no values for a device that is not in the forecast', () => {
    const series = toForecastSeries(RESPONSE, ['fc:9:pv_ac_kw']);
    expect(series['fc:9:pv_ac_kw'].timeseries?.every(point => point.value === null)).toBe(true);
  });
});
