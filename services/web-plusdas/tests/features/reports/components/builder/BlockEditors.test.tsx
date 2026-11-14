// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { DevicePointsEntry } from '@/api/types/devices';
import type { ReportBlock } from '@/api/types/reports';
import { AlarmEventsTableEditor, PointStatsTableEditor } from '@/features/reports/components/builder/BlockEditors';
import type { BuilderOptions } from '@/features/reports/types';

const OPTIONS: BuilderOptions = {
  points: [],
  devices: [
    { deviceId: 1, deviceName: 'meter_1', deviceType: 'METER' },
    { deviceId: 2, deviceName: 'bess_1', deviceType: 'BESS' },
  ] as DevicePointsEntry[],
  functions: [],
  alarms: [
    { id: 5, name: 'bess1_fault', severity: 'HIGH', message: 'BESS 1 faulted' },
    { id: 6, name: 'device_comm_loss', severity: 'HIGH', message: 'A device stopped communicating' },
  ],
  textVariables: {},
  siteName: 'Alpha',
  timeZone: 'UTC',
};

type Block<Kind extends ReportBlock['kind']> = Extract<ReportBlock, { kind: Kind }>;

describe('PointStatsTableEditor', () => {
  const block: Block<'point_stats_table'> = { kind: 'point_stats_table', id: 'stats_1', point_ids: [5], stats: ['max'], bucket: 'none' };

  it('keeps the statistics in their usual order whatever order they are ticked in', () => {
    const onChange = vi.fn();
    render(<PointStatsTableEditor block={block} options={OPTIONS} onChange={onChange} />);
    fireEvent.click(screen.getByRole('checkbox', { name: 'Min' }));
    expect(onChange).toHaveBeenLastCalledWith({ ...block, stats: ['min', 'max'] });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Max' }));
    expect(onChange).toHaveBeenLastCalledWith({ ...block, stats: [] });
  });

  it('adds and removes points, up to the limit', () => {
    const onChange = vi.fn();
    render(<PointStatsTableEditor block={block} options={OPTIONS} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: 'Add point' }));
    expect(onChange).toHaveBeenLastCalledWith({ ...block, point_ids: [5, 0] });
    fireEvent.click(screen.getByRole('button', { name: 'Remove point 1' }));
    expect(onChange).toHaveBeenLastCalledWith({ ...block, point_ids: [] });
  });
});

describe('AlarmEventsTableEditor', () => {
  const block: Block<'alarm_events_table'> = { kind: 'alarm_events_table', id: 'alarms_1', severity: null, alarm_ids: [6], limit: 200 };

  it("picks the site's defined alarms, none meaning all", () => {
    const onChange = vi.fn();
    render(<AlarmEventsTableEditor block={block} options={OPTIONS} onChange={onChange} />);
    expect(screen.getByRole('checkbox', { name: 'device_comm_loss' }).getAttribute('aria-checked')).toBe('true');
    fireEvent.click(screen.getByRole('checkbox', { name: 'bess1_fault' }));
    expect(onChange).toHaveBeenLastCalledWith({ ...block, alarm_ids: [6, 5] });
    fireEvent.click(screen.getByRole('checkbox', { name: 'device_comm_loss' }));
    expect(onChange).toHaveBeenLastCalledWith({ ...block, alarm_ids: [] });
  });

  it('says so when the site has no alarms', () => {
    render(<AlarmEventsTableEditor block={block} options={{ ...OPTIONS, alarms: [] }} onChange={vi.fn()} />);
    expect(screen.getByText('This site has no alarms defined.')).toBeTruthy();
    expect(screen.queryByRole('checkbox')).toBeNull();
  });

  it('keeps the row limit between 1 and 1000', () => {
    const onChange = vi.fn();
    render(<AlarmEventsTableEditor block={block} options={OPTIONS} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Rows at most'), { target: { value: '5000' } });
    expect(onChange).toHaveBeenLastCalledWith({ ...block, limit: 1000 });
    fireEvent.change(screen.getByLabelText('Rows at most'), { target: { value: '0' } });
    expect(onChange).toHaveBeenLastCalledWith({ ...block, limit: 1 });
  });
});
