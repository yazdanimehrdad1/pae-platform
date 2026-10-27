// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { devicesApi } from '@/api/devices';
import type { DevicePoint } from '@/api/types/devicePoints';
import { VirtualPointsList } from '@/features/devices/virtual/VirtualPointsList';

const formulaPoint = {
  id: 9, name: 'SITE_POWER', category: 'VIRTUAL', data_type: 'float32', unit: 'W',
  virtual_definition: { kind: 'calculation', function: 'sum', inputs: [1], scale: 1, offset: 0 },
  profile_point_key: null, profile_point_description: null,
} as unknown as DevicePoint;

const profilePoint = {
  id: 10, name: 'poi_apparent_power', category: 'VIRTUAL', data_type: 'float32', unit: 'kVA',
  virtual_definition: null, profile_point_key: 'poi_apparent_power',
  profile_point_description: 'Apparent power at the POI: √(P² + Q²)',
} as unknown as DevicePoint;

function renderList(points: DevicePoint[]) {
  vi.spyOn(devicesApi, 'getBySiteWithPoints').mockResolvedValue([]);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  render(<VirtualPointsList siteId="1001" points={points} onEdit={vi.fn()} onDelete={vi.fn()} />, { wrapper });
}

beforeEach(() => vi.restoreAllMocks());

describe('VirtualPointsList', () => {
  it('shows a site profile point by its description, with no edit or delete', () => {
    renderList([profilePoint]);

    expect(screen.getByText('site profile')).toBeTruthy();
    expect(screen.getByText('Apparent power at the POI: √(P² + Q²)')).toBeTruthy();
    expect(screen.queryByText('no definition')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Edit poi_apparent_power' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Delete poi_apparent_power' })).toBeNull();
  });

  it('falls back to the profile key when a profile point has no description', () => {
    renderList([{ ...profilePoint, profile_point_description: null } as DevicePoint]);
    expect(screen.getByText('Computed by the site profile (poi_apparent_power)')).toBeTruthy();
  });

  it('keeps edit and delete on a user formula point', () => {
    renderList([formulaPoint]);

    expect(screen.getByText('calculation')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Edit SITE_POWER' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Delete SITE_POWER' })).toBeTruthy();
  });
});
