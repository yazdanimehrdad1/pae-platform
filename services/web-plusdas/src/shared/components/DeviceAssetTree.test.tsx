// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { devicesApi } from '@/api/devices';
import type { DevicePointsEntry } from '@/api/types/devices';
import type { DevicePoint } from '@/api/types/devicePoints';
import { toast } from '@/shared/hooks/use-toast';
import { DeviceAssetTree } from './DeviceAssetTree';

vi.mock('@/shared/hooks/use-toast', () => ({ toast: vi.fn() }));

const point = (id: number, name: string, category: string, detail: Partial<DevicePoint> = {}) =>
  ({ id, name, category, data_type: 'uint16', ...detail } as DevicePoint);

const faultFlags = point(3, 'fault_flags', 'NATIVE', { data_type: 'bitfield16', bitfield_detail: { '0': 'overvoltage', '1': 'undervoltage' } });
const inverterState = point(4, 'inverter_state', 'NATIVE', { data_type: 'enum16', enum_detail: { '1': 'off' } });

const entry: DevicePointsEntry = {
  deviceId: 1,
  deviceName: 'bess-1',
  groups: {
    standardized: [point(1, 'BESS_ACTIVE_POWER', 'STANDARDIZED')],
    virtual: [],
    native: [faultFlags, inverterState, point(2, 'reg_1', 'NATIVE')],
  },
  points: [point(1, 'BESS_ACTIVE_POWER', 'STANDARDIZED'), faultFlags, inverterState, point(2, 'reg_1', 'NATIVE')],
};

function renderTree(props: Partial<Parameters<typeof DeviceAssetTree>[0]> = {}) {
  vi.spyOn(devicesApi, 'getBySiteWithPoints').mockResolvedValue([entry]);
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

    expect(onSelect).toHaveBeenCalledWith(['1'], { '1': 'BESS_ACTIVE_POWER' });
  });

  it('with expandBitfields, selects one bit of a bitfield point', async () => {
    const { onSelect } = renderTree({ expandBitfields: true });
    await openFolder('Native');
    fireEvent.click(screen.getByText('fault_flags'));
    fireEvent.click(screen.getByText('1 · undervoltage'));

    expect(onSelect).toHaveBeenCalledWith(['3:bit1'], { '3:bit1': 'fault_flags · undervoltage' });
  });

  it('with expandBitfields, the point checkbox toggles all its bits and shows partial selection', async () => {
    const { onSelect } = renderTree({ expandBitfields: true, selectedPoints: ['3:bit0'] });
    await openFolder('Native');
    const allBits = screen.getByLabelText('All bits of fault_flags');
    expect(allBits.getAttribute('data-state')).toBe('indeterminate');

    fireEvent.click(allBits.parentElement!);
    expect(onSelect).toHaveBeenCalledWith(['3:bit0', '3:bit1'], { '3:bit1': 'fault_flags · undervoltage' });
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

  it('marks enum points, and without expandBitfields lists a bitfield as one point', async () => {
    renderTree();
    await openFolder('Native');

    expect(screen.getByText('enum')).toBeTruthy();
    expect(screen.getByText('bits')).toBeTruthy();
    expect(screen.queryByText('0 · overvoltage')).toBeNull();
  });
});
