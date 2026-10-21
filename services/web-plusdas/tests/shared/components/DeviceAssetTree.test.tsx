// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { devicesApi } from '@/api/devices';
import { siteFunctionsApi } from '@/api/siteFunctions';
import type { SiteEndpointInfo } from '@/api/types/siteFunctions';
import type { DevicePointsEntry } from '@/api/types/devices';
import type { DevicePoint } from '@/api/types/devicePoints';
import { toast } from '@/shared/hooks/use-toast';
import { DeviceAssetTree } from '@/shared/components/DeviceAssetTree';

vi.mock('@/shared/hooks/use-toast', () => ({ toast: vi.fn() }));

const point = (id: number, name: string, category: string, detail: Partial<DevicePoint> = {}) =>
  ({ id, name, category, data_type: 'uint16', ...detail } as DevicePoint);

const faultFlags = point(3, 'fault_flags', 'NATIVE', { data_type: 'bitfield16', bitfield_detail: { '0': 'overvoltage', '1': 'undervoltage' } });
const inverterState = point(4, 'inverter_state', 'NATIVE', { data_type: 'enum16', enum_detail: { '1': 'off' } });

const entry: DevicePointsEntry = {
  deviceId: 1,
  deviceName: 'bess-1', deviceType: 'BESS',
  groups: {
    standardized: [point(1, 'BESS_ACTIVE_POWER', 'STANDARDIZED')],
    virtual: [],
    native: [faultFlags, inverterState, point(2, 'reg_1', 'NATIVE')],
  },
  points: [point(1, 'BESS_ACTIVE_POWER', 'STANDARDIZED'), faultFlags, inverterState, point(2, 'reg_1', 'NATIVE')],
};

const fn = (name: string, kind: SiteEndpointInfo['kind'], extra: Partial<SiteEndpointInfo> = {}): SiteEndpointInfo =>
  ({ name, kind, method: 'GET', summary: `${name} summary`, output: 'series', device_types: [], ...extra });

const functions: SiteEndpointInfo[] = [
  fn('site-poi-power', 'site'),
  fn('site-energy-summary', 'site', { output: 'scalar' }),
  fn('device-bess-trend', 'device', { device_types: ['BESS'] }),
  fn('device-pv-trend', 'device', { device_types: ['PV'] }),
  fn('device-any-trend', 'device'),
];

function renderTree(props: Partial<Parameters<typeof DeviceAssetTree>[0]> = {}) {
  vi.spyOn(devicesApi, 'getBySiteWithPoints').mockResolvedValue([entry]);
  vi.spyOn(siteFunctionsApi, 'list').mockResolvedValue({ site_id: 1001, profile: 'alpha_solar', endpoints: functions });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  const onSelect = vi.fn();
  render(<DeviceAssetTree siteId="1001" siteName="Site" selectedPoints={[]} onSelect={onSelect} {...props} />, { wrapper });
  return { onSelect };
}

async function openFolder(folderName: string) {
  fireEvent.click(await screen.findByText('bess-1'));
  fireEvent.click(screen.getByText(folderName));
}

beforeEach(() => vi.mocked(toast).mockClear());

describe('DeviceAssetTree', () => {
  it('lists a device\'s points in Standardized, Virtual, Native folders and hides empty ones', async () => {
    renderTree();
    fireEvent.click(await screen.findByText('bess-1'));

    const folders = screen.getAllByTestId(/^point-group-/).map(folder => folder.dataset.testid);
    expect(folders).toEqual(['point-group-standardized', 'point-group-native']);
    expect(screen.queryByText('Virtual')).toBeNull();
    expect(screen.queryByText('reg_1')).toBeNull();

    fireEvent.click(screen.getByText('Native'));
    expect(screen.getByText('reg_1')).toBeTruthy();
  });

  it('selects a point from inside its folder', async () => {
    const { onSelect } = renderTree();
    await openFolder('Standardized');
    fireEvent.click(screen.getByText('BESS_ACTIVE_POWER'));

    expect(onSelect).toHaveBeenCalledWith(['1'], { '1': 'bess-1-BESS_ACTIVE_POWER' });
  });

  it('with expandBitfields, clicking a bitfield point selects its raw value', async () => {
    const { onSelect } = renderTree({ expandBitfields: true });
    await openFolder('Native');
    fireEvent.click(screen.getByText('fault_flags'));

    expect(onSelect).toHaveBeenCalledWith(['3'], { '3': 'bess-1-fault_flags' });
    expect(screen.queryByText('0 · overvoltage')).toBeNull();
  });

  it('with expandBitfields, the chevron opens the bits as a subtree to select one', async () => {
    const { onSelect } = renderTree({ expandBitfields: true });
    await openFolder('Native');
    fireEvent.click(screen.getByRole('button', { name: 'Bits of fault_flags' }));
    expect(onSelect).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText('1 · undervoltage'));
    expect(onSelect).toHaveBeenCalledWith(['3:bit1'], { '3:bit1': 'bess-1-fault_flags · undervoltage' });
  });

  it('with expandBitfields, a collapsed bitfield says how many of its bits are selected', async () => {
    renderTree({ expandBitfields: true, selectedPoints: ['3:bit0', '3:bit1'] });
    await openFolder('Native');

    expect(screen.getByText('2 bits selected')).toBeTruthy();
  });

  it('lines every point row up: plain points get an empty expander slot of the same width', async () => {
    renderTree({ expandBitfields: true });
    await openFolder('Native');

    const rowOf = (name: string) => screen.getByText(name).parentElement!;
    for (const name of ['fault_flags', 'inverter_state', 'reg_1']) {
      expect(rowOf(name).style.paddingLeft).toBe('60px');
      expect(rowOf(name).firstElementChild!.className).toContain('w-4');
    }
  });

  it('refuses a selection past the limit and says why', async () => {
    const { onSelect } = renderTree({ expandBitfields: true, maxPoints: 1, selectedPoints: ['1'] });
    await openFolder('Native');
    fireEvent.click(screen.getByText('reg_1'));

    expect(onSelect).not.toHaveBeenCalled();
    expect(toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Point limit reached' }));
  });

  it('clears every selected point at once', async () => {
    const { onSelect } = renderTree({ selectedPoints: ['1', '3:bit0'] });
    expect(await screen.findByText('2 / 5 selected')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: /clear selection/i }));
    expect(onSelect).toHaveBeenCalledWith([], {});
  });

  it('disables Clear selection when nothing is selected', async () => {
    renderTree();
    const clearButton = await screen.findByRole('button', { name: /clear selection/i });
    expect((clearButton as HTMLButtonElement).disabled).toBe(true);
  });

  it('reveals a requested selection: expands down to it, scrolls to it and highlights it', async () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    renderTree({ expandBitfields: true, selectedPoints: ['3:bit1'], revealRequest: { selectionId: '3:bit1', requestId: 1 } });

    const bitRow = (await screen.findByText('1 · undervoltage')).parentElement!;
    expect(bitRow.className).toContain('ring-2');
    expect(scrollIntoView).toHaveBeenCalled();
    expect(screen.getByText('fault_flags')).toBeTruthy();
  });

  it('marks enum points, and without expandBitfields lists a bitfield as one point', async () => {
    renderTree();
    await openFolder('Native');

    expect(screen.getByText('enum')).toBeTruthy();
    expect(screen.getByText('bits')).toBeTruthy();
    expect(screen.queryByText('0 · overvoltage')).toBeNull();
  });

  describe('with includeFunctions', () => {
    it('lists only series functions: site ones under Site functions, device ones under devices of their type', async () => {
      renderTree({ includeFunctions: true });
      fireEvent.click(await screen.findByText('Site functions'));
      expect(screen.getByText('site-poi-power')).toBeTruthy();
      expect(screen.queryByText('site-energy-summary')).toBeNull();

      fireEvent.click(screen.getByText('bess-1'));
      fireEvent.click(screen.getByText('Functions'));
      expect(screen.getByText('device-bess-trend')).toBeTruthy();
      expect(screen.getByText('device-any-trend')).toBeTruthy();
      expect(screen.queryByText('device-pv-trend')).toBeNull();
    });

    it('selects a site function and a device function with their own ids and labels', async () => {
      const { onSelect } = renderTree({ includeFunctions: true });
      fireEvent.click(await screen.findByText('Site functions'));
      fireEvent.click(screen.getByText('site-poi-power'));
      expect(onSelect).toHaveBeenLastCalledWith(['fn:site-poi-power'], { 'fn:site-poi-power': 'site-poi-power' });

      fireEvent.click(screen.getByText('bess-1'));
      fireEvent.click(screen.getByText('Functions'));
      fireEvent.click(screen.getByText('device-any-trend'));
      expect(onSelect).toHaveBeenLastCalledWith(['fn:1:device-any-trend'], { 'fn:1:device-any-trend': 'bess-1-device-any-trend' });
    });

    it('counts a function toward the point limit', async () => {
      const { onSelect } = renderTree({ includeFunctions: true, maxPoints: 1, selectedPoints: ['1'] });
      fireEvent.click(await screen.findByText('Site functions'));
      fireEvent.click(screen.getByText('site-poi-power'));

      expect(onSelect).not.toHaveBeenCalled();
      expect(toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Point limit reached' }));
    });

    it('shows no functions without the flag, and does not ask for them', async () => {
      renderTree();
      await screen.findByText('bess-1');
      expect(screen.queryByText('Site functions')).toBeNull();
      expect(siteFunctionsApi.list).not.toHaveBeenCalled();
    });
  });
});

describe('DeviceAssetTree PV forecast (site_level)', () => {
  const pvEntry: DevicePointsEntry = {
    deviceId: 4, deviceName: 'pv1', deviceType: 'PV',
    groups: { standardized: [], virtual: [], native: [point(9, 'W', 'NATIVE')] },
    points: [point(9, 'W', 'NATIVE')],
  };
  const pvArray = {
    device_id: 4, site_id: 1001, device_name: 'pv1', device_type: 'PV' as const,
    tilt_deg: 25, azimuth_deg: 180, dc_capacity_kw: 6500, ac_capacity_kw: 5000,
    system_loss_pct: 14, temp_coefficient_pct_per_c: -0.35,
    created_at: '2026-10-20T00:00:00Z', updated_at: '2026-10-20T00:00:00Z',
  };

  function renderForecastTree(arrays = [pvArray]) {
    vi.spyOn(devicesApi, 'getBySiteWithPoints').mockResolvedValue([entry, pvEntry]);
    vi.spyOn(devicesApi, 'getSitePvArrays').mockResolvedValue(arrays);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    const onSelect = vi.fn();
    render(<DeviceAssetTree siteId="1001" siteName="Site" selectedPoints={[]} onSelect={onSelect} includeForecast />, { wrapper });
    return { onSelect };
  }

  it('lists the site AC power, the AC power of each PV device and the weather under site_level', async () => {
    const { onSelect } = renderForecastTree();
    fireEvent.click(await screen.findByText('site_level'));
    fireEvent.click(screen.getByText('PV forecast'));
    const rows = Array.from(screen.getByTestId('pv-forecast').querySelectorAll('[data-selection-id]'))
      .map(row => row.getAttribute('data-selection-id'));
    expect(rows).toEqual([
      'fc:site:pv_ac_kw', 'fc:4:pv_ac_kw', 'fc:site:ghi', 'fc:site:temp_air_c', 'fc:site:wind_speed_ms', 'fc:site:cloud_cover_pct',
    ]);

    fireEvent.click(screen.getByText('PV AC power'));
    expect(onSelect).toHaveBeenLastCalledWith(['fc:site:pv_ac_kw'], { 'fc:site:pv_ac_kw': 'Forecast · PV AC power' });
    fireEvent.click(screen.getByText('pv1 · AC power'));
    expect(onSelect).toHaveBeenLastCalledWith(['fc:4:pv_ac_kw'], { 'fc:4:pv_ac_kw': 'Forecast · pv1 · AC power' });
  });

  it('has no site_level folder when the site has no PV arrays', async () => {
    renderForecastTree([]);
    expect(await screen.findByText('pv1')).toBeTruthy();
    expect(screen.queryByText('site_level')).toBeNull();
  });

  it('reveals a selected per-device forecast series', async () => {
    vi.spyOn(devicesApi, 'getBySiteWithPoints').mockResolvedValue([entry, pvEntry]);
    vi.spyOn(devicesApi, 'getSitePvArrays').mockResolvedValue([pvArray]);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    render(
      <DeviceAssetTree siteId="1001" siteName="Site" selectedPoints={['fc:4:pv_ac_kw']} onSelect={vi.fn()} includeForecast
        revealRequest={{ selectionId: 'fc:4:pv_ac_kw', requestId: 1 }} />,
      { wrapper },
    );
    expect(await screen.findByText('pv1 · AC power')).toBeTruthy();
  });
});
