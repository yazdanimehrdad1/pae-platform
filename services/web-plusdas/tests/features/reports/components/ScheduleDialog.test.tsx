// @vitest-environment jsdom
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import type { ReportScheduleRecord, ReportTemplateRecord } from '@/api/types/reports';
import { ScheduleDialog } from '@/features/reports/components/ScheduleDialog';

const TEMPLATE: ReportTemplateRecord = {
  id: 4, site_id: 1001, name: 'Daily energy', description: '', version: 1,
  created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z',
  definition: { schema_version: 1, window: { kind: 'calendar', period: 'day', offset: -1 }, blocks: [{ kind: 'text', id: 'intro', body: 'x' }] },
};

const SCHEDULE: ReportScheduleRecord = {
  id: 2, site_id: 1001, template_id: 4, template_name: 'Daily energy', timezone: 'America/Los_Angeles',
  cadence: { kind: 'weekly', time: '07:30', weekdays: [0] }, window_override: null, enabled: true, keep_last: 5, keep_days: null,
  next_run_at: '2026-10-19T14:30:00Z', last_run_at: null, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z',
};

beforeAll(() => {
  Element.prototype.scrollIntoView ??= () => {};
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => {};
});

function renderDialog(schedule: ReportScheduleRecord | null) {
  const onSave = vi.fn();
  render(
    <ScheduleDialog open onOpenChange={() => {}} schedule={schedule} templateId={4} templates={[TEMPLATE]}
      timeZone="America/Los_Angeles" isSaving={false} onSave={onSave} />,
  );
  return onSave;
}

describe('ScheduleDialog', () => {
  it('creates a daily schedule for the template, keeping the last 30 by default', () => {
    const onSave = renderDialog(null);
    expect(screen.getByText(/on the site's clock \(America\/Los_Angeles\)/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText('At'), { target: { value: '05:45' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create schedule' }));
    expect(onSave).toHaveBeenCalledWith({
      template_id: 4, cadence: { kind: 'daily', time: '05:45' }, window_override: null, enabled: true, keep_last: 30, keep_days: null,
    });
  });

  it('changes weekdays and retention of an existing schedule', () => {
    const onSave = renderDialog(SCHEDULE);
    fireEvent.click(screen.getByRole('checkbox', { name: 'Friday' }));
    fireEvent.change(screen.getByLabelText('The last'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('Days at most'), { target: { value: '90' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save schedule' }));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      cadence: { kind: 'weekly', time: '07:30', weekdays: [0, 4] }, keep_last: null, keep_days: 90,
    }));
  });

  it('needs a weekday for a weekly schedule', () => {
    renderDialog(SCHEDULE);
    fireEvent.click(screen.getByRole('checkbox', { name: 'Monday' }));
    expect(screen.getByText('Choose at least one weekday')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Save schedule' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("covers the template's period unless another is chosen", () => {
    const onSave = renderDialog(null);
    const usesTemplate = screen.getByRole('checkbox', { name: "The template's period (Yesterday)" });
    fireEvent.click(usesTemplate);
    expect(screen.getByLabelText('Period')).toBeTruthy(); // the period editor appears
    fireEvent.click(screen.getByRole('button', { name: 'Create schedule' }));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ window_override: { kind: 'calendar', period: 'day', offset: -1 } }));
  });
});
