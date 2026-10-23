import type { components } from '@contracts/intelli-gateway';

type Schemas = components['schemas'];

// Wire types: generated from intelli-gateway's contract, never hand-written.
export type PvForecastResponse = Schemas['PvForecastResponse'];
export type ForecastInterval = Schemas['ForecastIntervalResponse'];
export type ForecastArrayInterval = Schemas['ArrayIntervalResponse'];

// The forecast series the Historian offers. Keys are the contract's field names (a Record, so a
// renamed field fails the typecheck); values are the labels shown in the asset tree.
// Site: the site's AC power (all PV devices) and its weather.
export type SiteForecastVariable = keyof Pick<
  ForecastInterval,
  'pv_ac_kw' | 'ghi' | 'temp_air_c' | 'wind_speed_ms' | 'cloud_cover_pct'
>;
// Per PV device (one array per PV or INVERTER device in backend-ot): its AC power.
export type DeviceForecastVariable = keyof Pick<ForecastArrayInterval, 'pv_ac_kw'>;

export const SITE_FORECAST_VARIABLES: Record<SiteForecastVariable, string> = {
  pv_ac_kw: 'PV AC power',
  ghi: 'Solar irradiance (GHI)',
  temp_air_c: 'Air temperature',
  wind_speed_ms: 'Wind speed',
  cloud_cover_pct: 'Cloud cover',
};

export const DEVICE_FORECAST_VARIABLES: Record<DeviceForecastVariable, string> = {
  pv_ac_kw: 'AC power',
};
