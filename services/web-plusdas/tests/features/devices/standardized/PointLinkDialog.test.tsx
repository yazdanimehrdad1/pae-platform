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
  { id: 16, name: 'AL1', category: 'NATIVE', unit: 'A', record_enabled: false },
] as unknown as DevicePoint[];
const scaleInput = () => screen.getByLabelText('Scale (×)') as HTMLInputElement;
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

  it('keeps the scale the user typed when the unit changes, and saves any unit and scale', async () => {
    const link = vi.spyOn(devicesApi, 'linkPoint').mockResolvedValue(linked);
    const { onOpenChange } = renderDialog(linked);

    expect(scaleInput().value).toBe('0.001');
    fireEvent.change(screen.getByLabelText('Unit'), { target: { value: 'W' } });
    expect(scaleInput().value).toBe('0.001');
    fireEvent.change(screen.getByLabelText('Unit'), { target: { value: 'kW' } });
    fireEvent.change(scaleInput(), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save link' }));

    await waitFor(() => expect(link).toHaveBeenCalledWith('1001', 2, 57, { source_point_id: 14, unit: 'kW', scale_factor: 2 }));
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  it('suggests the power conversion, and "Use" fills it in', () => {
    renderDialog(linked);
    expect(screen.queryByText(/Suggested for/)).toBeNull();

    fireEvent.change(scaleInput(), { target: { value: '1' } });
    expect(screen.getByText('Suggested for W → kW: × 0.001')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Use' }));
    expect(scaleInput().value).toBe('0.001');
    expect(screen.queryByText(/Suggested for/)).toBeNull();

    fireEvent.change(screen.getByLabelText('Unit'), { target: { value: 'my unit' } });
    expect(screen.queryByText(/Suggested for/)).toBeNull();
  });

  it('still refuses a scale that is not a number', async () => {
    const link = vi.spyOn(devicesApi, 'linkPoint');
    renderDialog(linked);
    fireEvent.change(scaleInput(), { target: { value: 'abc' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save link' }));
    expect(await screen.findByText('Enter a number.')).toBeTruthy();
    expect(link).not.toHaveBeenCalled();
  });

  it('warns when the chosen source is not recorded, and still saves', async () => {
    const link = vi.spyOn(devicesApi, 'linkPoint').mockResolvedValue(linked);
    renderDialog({ ...linked, source_point_id: 16, unit: 'A', scale_factor: 1 } as unknown as DevicePoint);
    expect(screen.getByText(/isn't recorded, so the link shows no readings/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Save link' }));
    await waitFor(() => expect(link).toHaveBeenCalledWith('1001', 2, 57, { source_point_id: 16, unit: 'A', scale_factor: 1 }));
  });
});
