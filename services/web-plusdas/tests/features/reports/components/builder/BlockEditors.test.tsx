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
  const block: Block<'alarm_events_table'> = { kind: 'alarm_events_table', id: 'alarms_1', severity: null, device_ids: [2], limit: 200 };

  it('filters by the ticked devices, none meaning all', () => {
    const onChange = vi.fn();
    render(<AlarmEventsTableEditor block={block} options={OPTIONS} onChange={onChange} />);
    fireEvent.click(screen.getByRole('checkbox', { name: 'meter_1' }));
    expect(onChange).toHaveBeenLastCalledWith({ ...block, device_ids: [2, 1] });
    fireEvent.click(screen.getByRole('checkbox', { name: 'bess_1' }));
    expect(onChange).toHaveBeenLastCalledWith({ ...block, device_ids: [] });
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
