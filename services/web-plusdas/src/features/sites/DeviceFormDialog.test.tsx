// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { DeviceRecord } from '@/shared/types/device';
import { DeviceFormDialog } from './DeviceFormDialog';

// backend-ot returns canonical uppercase types; the seeded devices are PV and BESS, which the
// form's old lowercase meter/relay/inverter list did not include.
const pvDevice: DeviceRecord = {
  device_id: 1,
  site_id: 1001,
  name: 'mock-device-1',
  type: 'PV',
  protocol: 'Modbus',
  vendor: null,
  model: null,
  host: 'mock-modbus',
  port: 502,
  server_address: 1,
  poll_enabled: true,
  read_from_aggregator: true,
  modbus_address_mode: 'one_based',
  scan_ranges_locked: false,
  created_at: '2026-09-24T00:00:00Z',
  updated_at: '2026-09-25T00:00:00Z',
};

describe('DeviceFormDialog', () => {
  it('submits an edit of a PV device with its canonical type', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<DeviceFormDialog open onOpenChange={() => {}} device={pvDevice} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'PV inverter 1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      name: 'PV inverter 1',
      type: 'PV',
      protocol: 'Modbus',
      host: 'mock-modbus',
      modbus_address_mode: 'one_based',
    });
  });

  it('sends only the fields that were filled in for a new device', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<DeviceFormDialog open onOpenChange={() => {}} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'meter-1' } });
    fireEvent.change(screen.getByLabelText('Host'), { target: { value: '10.0.0.5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const payload = onSubmit.mock.calls[0][0];
    expect(payload).toMatchObject({ name: 'meter-1', type: 'METER', host: '10.0.0.5', port: 502 });
    expect(payload).not.toHaveProperty('vendor');
    expect(payload).not.toHaveProperty('timeout');
  });

  it('does not submit without the required fields', async () => {
    const onSubmit = vi.fn();
    render(<DeviceFormDialog open onOpenChange={() => {}} onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findAllByText('Required')).not.toHaveLength(0);
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
