// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AnswerMarkdown } from '@/features/assistant/components/AnswerMarkdown';

// The AI's answer is Markdown: a table, bullets and bold render as such; HTML in it never does.

const ANSWER = [
  'Warning: BESS 2 is derating.',
  '',
  '| Device | Point | Value | Unit |',
  '|---|---|---|---|',
  '| BESS 1 | active_power | 250.0 | kW |',
  '| BESS 2 | active_power | 120.0 | kW |',
  '',
  '- Cabinet temperature 41 °C (stale, last reading 13:05 PST)',
  '',
  '**Safety:** isolate before opening the cabinet.',
  '',
  'Based on: bess1.active_power, bess2.active_power, 14:00-14:20 PST',
].join('\n');

describe('AnswerMarkdown', () => {
  it('renders a table, a list and bold text', () => {
    render(<AnswerMarkdown text={ANSWER} />);
    const table = screen.getByRole('table');
    expect(screen.getAllByRole('columnheader').map(cell => cell.textContent)).toEqual(['Device', 'Point', 'Value', 'Unit']);
    expect(table.querySelectorAll('tbody tr')).toHaveLength(2);
    expect(screen.getByRole('cell', { name: '120.0' })).toBeTruthy();
    expect(screen.getByRole('listitem').textContent).toContain('stale, last reading 13:05 PST');
    expect(screen.getByText('Safety:').tagName).toBe('STRONG');
  });

  it('keeps HTML in the answer as text', () => {
    const { container } = render(<AnswerMarkdown text={'<img src=x onerror="alert(1)"> <script>alert(2)</script>'} />);
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('script')).toBeNull();
  });
});
