// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { devicesApi } from '@/api/devices';
import type { DevicePoint } from '@/api/types/devicePoints';
import { PointLinkDialog } from '@/features/devices/standardized/PointLinkDialog';

vi.mock('@/shared/hooks/use-toast', () => ({ toast: vi.fn() }));

const sources = [
  { id: 14, name: 'W', category: 'NATIVE', unit: 'W' },
  { id: 15, name: 'SoC', category: 'NATIVE', unit: '%' },
] as unknown as DevicePoint[];
const linked = {
  id: 57, name: 'BESS_ACTIVE_POWER', category: 'STANDARDIZED', source_point_id: 14, unit: 'kW', scale_factor: 0.001,
} as unknown as DevicePoint;
const unlinked = { id: 58, name: 'BESS_STATE_OF_CHARGE', category: 'STANDARDIZED' } as unknown as DevicePoint;

function renderDialog(point: DevicePoint) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  const onOpenChange = vi.fn();
  render(<PointLinkDialog open onOpenChange={onOpenChange} siteId="1001" deviceId={2} point={point} sources={sources} />, { wrapper });
  return { onOpenChange };
}

beforeEach(() => vi.restoreAllMocks());

describe('PointLinkDialog', () => {
  it('does not save without a source and says so', async () => {
    const link = vi.spyOn(devicesApi, 'linkPoint');
    renderDialog(unlinked);
    fireEvent.click(screen.getByRole('button', { name: 'Save link' }));
    expect(await screen.findByText('Pick the point this one shows.')).toBeTruthy();
    expect(link).not.toHaveBeenCalled();
  });

  it('fills in the power scale when the unit changes, and saves through the link route', async () => {
    const link = vi.spyOn(devicesApi, 'linkPoint').mockResolvedValue(linked);
    const { onOpenChange } = renderDialog(linked);

    expect((screen.getByLabelText('Scale (×)') as HTMLInputElement).value).toBe('0.001');
    fireEvent.change(screen.getByLabelText('Unit'), { target: { value: 'W' } });
    expect((screen.getByLabelText('Scale (×)') as HTMLInputElement).value).toBe('1');
    fireEvent.change(screen.getByLabelText('Unit'), { target: { value: 'kW' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save link' }));

    await waitFor(() => expect(link).toHaveBeenCalledWith('1001', 2, 57, { source_point_id: 14, unit: 'kW', scale_factor: 0.001 }));
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it('blocks a typed scale that does not convert the power units', async () => {
    const link = vi.spyOn(devicesApi, 'linkPoint');
    renderDialog(linked);
    fireEvent.change(screen.getByLabelText('Scale (×)'), { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save link' }));
    expect(await screen.findByText('W to kW needs a scale of 0.001.')).toBeTruthy();
    expect(link).not.toHaveBeenCalled();
  });
});
