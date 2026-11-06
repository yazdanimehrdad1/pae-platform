// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { devicesApi } from '@/api/devices';
import { PointsCsvActions } from '@/features/devices/csv/PointsCsvActions';
import * as download from '@/shared/lib/download';

vi.mock('@/shared/hooks/use-toast', () => ({ toast: vi.fn() }));
const role = vi.hoisted(() => ({ current: 'engineer' }));
vi.mock('@/shared/contexts/auth', () => ({
  useAuth: () => ({ user: { id: 'u1', name: 'Test', email: 't@example.com', role: role.current } }),
}));

const CSV = 'name,poll_kind,address,data_type\r\nW,holding,0,int16\r\n';

function renderActions() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  render(
    <PointsCsvActions siteId="1001" deviceId={4} deviceName="2bess_1pv-bess1" onImported={vi.fn()} />,
    { wrapper },
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  role.current = 'engineer';
});

describe('PointsCsvActions', () => {
  it('downloads the template and the export', async () => {
    const save = vi.spyOn(download, 'downloadFile').mockImplementation(() => {});
    vi.spyOn(devicesApi, 'pointsCsvTemplate').mockResolvedValue('header\r\n');
    vi.spyOn(devicesApi, 'exportPointsCsv').mockResolvedValue(CSV);
    renderActions();
    fireEvent.click(screen.getByRole('button', { name: /template/i }));
    await waitFor(() =>
      expect(save).toHaveBeenCalledWith('device-points-template.csv', 'header\r\n', 'text/csv;charset=utf-8'));
    fireEvent.click(screen.getByRole('button', { name: /export csv/i }));
    await waitFor(() =>
      expect(save).toHaveBeenLastCalledWith('2bess_1pv-bess1-points.csv', CSV, 'text/csv;charset=utf-8'));
    expect(devicesApi.exportPointsCsv).toHaveBeenCalledWith('1001', 4);
  });

  it.each([['admin', true], ['engineer', true], ['monitor', false]])(
    'import is for admins and engineers (%s: %s); everyone downloads',
    (userRole, canImport) => {
      role.current = userRole;
      renderActions();
      expect(screen.queryByRole('button', { name: /import csv/i }) !== null).toBe(canImport);
      expect(screen.getByRole('button', { name: /template/i })).toBeTruthy();
      expect(screen.getByRole('button', { name: /export csv/i })).toBeTruthy();
    },
  );

  it('a picked file opens the import preview', async () => {
    const importCsv = vi.spyOn(devicesApi, 'importPointsCsv').mockResolvedValue({
      applied: false, created: [], updated: [], unchanged: ['W'], missing: [], deleted: [], errors: [],
    });
    renderActions();
    const file = new File([CSV], 'points.csv', { type: 'text/csv' });
    fireEvent.change(screen.getByLabelText('CSV file to import'), { target: { files: [file] } });
    expect(await screen.findByText('Import points from CSV')).toBeTruthy();
    await waitFor(() =>
      expect(importCsv).toHaveBeenCalledWith('1001', 4, CSV, { dryRun: true, deleteMissing: false }));
  });
});
