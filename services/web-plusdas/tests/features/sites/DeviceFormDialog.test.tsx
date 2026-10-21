// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { DeviceRecord, PvArrayConfig } from '@/api/types/devices';
import { DeviceFormDialog } from '@/features/sites/DeviceFormDialog';

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

const PV_ARRAY: PvArrayConfig = {
  device_id: 1, site_id: 1001, device_name: 'mock-device-1', device_type: 'PV',
  tilt_deg: 25, azimuth_deg: 180, dc_capacity_kw: 6500, ac_capacity_kw: 5000,
  system_loss_pct: 12, temp_coefficient_pct_per_c: -0.4,
  created_at: '2026-10-20T00:00:00Z', updated_at: '2026-10-20T00:00:00Z',
};
const meterDevice: DeviceRecord = { ...pvDevice, type: 'METER' };

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe('DeviceFormDialog PV array', () => {
  it('shows the PV array of a PV device and sends it back', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<DeviceFormDialog open onOpenChange={() => {}} device={pvDevice} pvArray={PV_ARRAY} onSubmit={onSubmit} />);

    expect((screen.getByLabelText('Tilt (deg)') as HTMLInputElement).value).toBe('25');
    fill('Tilt (deg)', '10');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][1]).toEqual({
      tilt_deg: 10, azimuth_deg: 180, dc_capacity_kw: 6500, ac_capacity_kw: 5000,
      system_loss_pct: 12, temp_coefficient_pct_per_c: -0.4,
    });
  });

  it('sends no PV array when its fields are blank, and defaults the optional ones', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<DeviceFormDialog open onOpenChange={() => {}} device={pvDevice} onSubmit={onSubmit} />);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][1]).toBeNull();

    fill('Tilt (deg)', '20');
    fill('Azimuth (deg)', '170');
    fill('DC capacity (kWp)', '1000');
    fill('AC capacity (kW)', '800');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(2));
    expect(onSubmit.mock.calls[1][1]).toEqual({
      tilt_deg: 20, azimuth_deg: 170, dc_capacity_kw: 1000, ac_capacity_kw: 800,
      system_loss_pct: 14, temp_coefficient_pct_per_c: -0.35,
    });
  });

  it('refuses a partial or out-of-range PV array', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<DeviceFormDialog open onOpenChange={() => {}} device={pvDevice} onSubmit={onSubmit} />);

    fill('Tilt (deg)', '95');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Enter 0 to 90')).toBeTruthy();
    expect(screen.getAllByText(/^Enter /).length).toBeGreaterThan(1); // azimuth, DC, AC missing
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('has no PV array section for other device types', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<DeviceFormDialog open onOpenChange={() => {}} device={meterDevice} onSubmit={onSubmit} />);

    expect(screen.queryByLabelText('Tilt (deg)')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][1]).toBeNull();
  });
});
