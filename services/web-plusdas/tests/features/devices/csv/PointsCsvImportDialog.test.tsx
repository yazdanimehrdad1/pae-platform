// @vitest-environment jsdom
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { devicesApi } from '@/api/devices';
import type { PointsCsvImportResult } from '@/api/types/devicePoints';
import { PointsCsvImportDialog } from '@/features/devices/csv/PointsCsvImportDialog';
import { toast } from '@/shared/hooks/use-toast';

vi.mock('@/shared/hooks/use-toast', () => ({ toast: vi.fn() }));

const FILE = { name: 'bess1-points.csv', text: 'name,poll_kind,address,data_type\r\n', id: 1 };
const PLAN: PointsCsvImportResult = {
  applied: false,
  created: ['New'],
  updated: [{ name: 'W', fields: ['unit'] }],
  unchanged: ['SoC', 'Hz'],
  missing: ['Old'],
  deleted: [],
  errors: [],
};

function renderDialog() {
  const onImported = vi.fn();
  const onClose = vi.fn();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  render(
    <PointsCsvImportDialog file={FILE} siteId="1001" deviceId={4} onClose={onClose} onImported={onImported} />,
    { wrapper },
  );
  return { onImported, onClose };
}

const applyButton = () => screen.getByRole('button', { name: /apply/i }) as HTMLButtonElement;

beforeEach(() => {
  vi.restoreAllMocks();
  vi.mocked(toast).mockClear();
});

describe('PointsCsvImportDialog', () => {
  it('previews the plan from a dry run; points not in the file stay unless ticked', async () => {
    const importCsv = vi.spyOn(devicesApi, 'importPointsCsv').mockResolvedValue(PLAN);
    renderDialog();
    expect(await screen.findByText('New (1)')).toBeTruthy();
    expect(screen.getByText('W (unit)')).toBeTruthy();
    expect(screen.getByText('2 points unchanged.')).toBeTruthy();
    expect(screen.getByText('Not in the file (1)')).toBeTruthy();
    expect(importCsv).toHaveBeenCalledWith('1001', 4, FILE.text, { dryRun: true, deleteMissing: false });
    expect(applyButton().disabled).toBe(false);
  });

  it('lists every problem with its line and column, and disables Apply', async () => {
    vi.spyOn(devicesApi, 'importPointsCsv').mockResolvedValue({
      ...PLAN,
      errors: [
        { line: 2, column: 'data_type', message: 'data_type int8 is not a data type' },
        { line: 3, column: 'name', message: 'W is also on line 2' },
      ],
    });
    renderDialog();
    expect(await screen.findByText(/2 problems in the file/)).toBeTruthy();
    expect(screen.getByText('W is also on line 2')).toBeTruthy();
    expect(screen.getByText('data_type')).toBeTruthy();
    expect(applyButton().disabled).toBe(true);
  });

  it('applies with the delete choice, refreshes the points and says what changed', async () => {
    const importCsv = vi.spyOn(devicesApi, 'importPointsCsv').mockImplementation(async (_site, _device, _text, opts) =>
      opts.dryRun ? PLAN : { ...PLAN, applied: true, deleted: opts.deleteMissing ? ['Old'] : [] });
    const { onImported, onClose } = renderDialog();
    fireEvent.click(await screen.findByRole('checkbox', { name: 'Delete these' }));
    await waitFor(() =>
      expect(importCsv).toHaveBeenCalledWith('1001', 4, FILE.text, { dryRun: true, deleteMissing: true }));
    await waitFor(() => expect(applyButton().disabled).toBe(false));
    fireEvent.click(applyButton());
    await waitFor(() => expect(onImported).toHaveBeenCalled());
    expect(importCsv).toHaveBeenLastCalledWith('1001', 4, FILE.text, { dryRun: false, deleteMissing: true });
    expect(toast).toHaveBeenCalledWith({ title: 'Points imported', description: '1 point added, 1 point updated, 1 point deleted' });
    expect(onClose).toHaveBeenCalled();
  });

  it('says when the file matches the device', async () => {
    vi.spyOn(devicesApi, 'importPointsCsv').mockResolvedValue({ ...PLAN, created: [], updated: [], missing: [] });
    renderDialog();
    expect(await screen.findByText('The file matches the device: nothing to import.')).toBeTruthy();
    expect(applyButton().disabled).toBe(true);
  });
});
