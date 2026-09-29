// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { devicesApi } from '@/api/devices';
import type { DevicePoint } from '@/api/types/devicePoints';
import { VirtualPointDialog } from './VirtualPointDialog';

vi.mock('@/shared/hooks/use-toast', () => ({ toast: vi.fn() }));

const calculationPoint = {
  id: 9, name: 'SITE_POWER', category: 'VIRTUAL', data_type: 'float32', unit: 'W',
  virtual_definition: { kind: 'calculation', function: 'sum', inputs: [1, 3], scale: 1, offset: 0 },
} as unknown as DevicePoint;

function renderDialog(point: DevicePoint | null = null) {
  vi.spyOn(devicesApi, 'getBySiteWithPoints').mockResolvedValue([{
    deviceId: 2, deviceName: 'bess', groups: { standardized: [], virtual: [], native: [] },
    points: [
      { id: 1, name: 'power_a', category: 'NATIVE', data_type: 'uint16', unit: 'W' },
      { id: 3, name: 'power_b', category: 'NATIVE', data_type: 'uint16', unit: 'W' },
    ] as unknown as DevicePoint[],
  }]);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  const onOpenChange = vi.fn();
  render(<VirtualPointDialog open onOpenChange={onOpenChange} siteId="1001" deviceId={2} point={point} />, { wrapper });
  return { onOpenChange };
}

beforeEach(() => vi.restoreAllMocks());

describe('VirtualPointDialog', () => {
  it('does not save an incomplete new point and says what is missing', async () => {
    const create = vi.spyOn(devicesApi, 'createVirtualPoint');
    renderDialog();
    fireEvent.click(screen.getByRole('button', { name: 'Create virtual point' }));

    await waitFor(() => expect(screen.getAllByRole('alert').map(alert => alert.textContent)).toContain('Choose a point'));
    expect(document.getElementById('virtual-name-error')?.textContent).toBe('Required');
    expect(create).not.toHaveBeenCalled();
  });

  it('edits an existing calculation and saves it through the virtual route', async () => {
    const update = vi.spyOn(devicesApi, 'updateVirtualPoint').mockResolvedValue(calculationPoint);
    const { onOpenChange } = renderDialog(calculationPoint);

    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('SITE_POWER');
    expect(await screen.findByText('Sum of bess · power_a, bess · power_b')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Scale (×)'), { target: { value: '0.001' } });
    fireEvent.change(screen.getByLabelText('Unit'), { target: { value: 'kW' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(update).toHaveBeenCalledTimes(1));
    expect(update).toHaveBeenCalledWith('1001', 2, 9, {
      name: 'SITE_POWER', unit: 'kW',
      definition: { kind: 'calculation', function: 'sum', inputs: [1, 3], scale: 0.001, offset: 0 },
    });
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it('adds and removes cases of a condition', () => {
    renderDialog();
    expect(screen.getAllByTestId('virtual-case')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Case' }));
    expect(screen.getAllByTestId('virtual-case')).toHaveLength(2);
    expect((screen.getAllByLabelText('Output')[1] as HTMLInputElement).value).toBe('2');
    fireEvent.click(screen.getByRole('button', { name: 'Remove case 2' }));
    expect(screen.getAllByTestId('virtual-case')).toHaveLength(1);
  });
});
