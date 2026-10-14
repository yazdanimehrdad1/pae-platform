import { describe, expect, it } from 'vitest';
import type { ReportDefinition, ReportTemplateRecord } from '@/api/types/reports';
import {
  blankDefinition,
  draftProblems,
  errorsByBlock,
  moveBlock,
  newBlock,
  nextBlockId,
  runRequest,
  validationErrors,
} from '@/features/reports/lib/draft';

const TEMPLATE: ReportTemplateRecord = {
  id: 4, site_id: 1001, name: 'Daily', description: '', version: 2,
  created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z',
  definition: blankDefinition(),
};

describe('block ids', () => {
  it('use the first number no block has, per kind', () => {
    const blocks = [newBlock('chart', []), { ...newBlock('chart', []), id: 'chart_3' }];
    expect(nextBlockId('chart', blocks)).toBe('chart_2');
    expect(nextBlockId('point_stats_table', blocks)).toBe('stats_1');
  });

  it('match what backend-ot accepts', () => {
    for (const kind of ['text', 'kpi', 'chart', 'point_stats_table', 'alarm_events_table'] as const) {
      expect(newBlock(kind, []).id).toMatch(/^[a-z][a-z0-9_]{0,39}$/);
    }
  });
});

describe('draftProblems', () => {
  it('has none for the blank report', () => {
    expect(draftProblems(blankDefinition()).size).toBe(0);
  });

  it('names what is still to choose, per block (new blocks start with an unset point)', () => {
    const definition: ReportDefinition = {
      ...blankDefinition(),
      blocks: [newBlock('chart', []), newBlock('kpi', []), newBlock('point_stats_table', []), { kind: 'text', id: 'text_1', body: ' ' }, newBlock('alarm_events_table', [])],
    };
    expect(Object.fromEntries(draftProblems(definition))).toEqual({
      chart_1: ['Series 1: choose a point'],
      kpis_1: ['Figure 1: choose a point'],
      stats_1: ['Choose every point'],
      text_1: ['Write the text'],
    });
  });

  it('needs a function and a value for a site function figure', () => {
    const definition: ReportDefinition = {
      ...blankDefinition(),
      blocks: [{ kind: 'kpi', id: 'kpis_1', items: [{ source: 'site_function', function: 'site-energy-summary', field: '' }] }],
    };
    expect(draftProblems(definition).get('kpis_1')).toEqual(['Figure 1: choose a function and a value']);
  });

  it('needs a custom range that ends after it starts', () => {
    const definition: ReportDefinition = { ...blankDefinition(), window: { kind: 'fixed', start_time: '2026-10-02T00:00:00Z', end_time: '2026-10-01T00:00:00Z' } };
    expect(draftProblems(definition).get('window')).toEqual(['The period must end after it starts']);
  });
});

describe('moveBlock', () => {
  it('swaps with the neighbour and stays put at the ends', () => {
    const blocks = [newBlock('text', []), { ...newBlock('chart', []), series: [{ source: 'point' as const, point_id: 5 }] }];
    expect(moveBlock(blocks, 0, 1).map(block => block.kind)).toEqual(['chart', 'text']);
    expect(moveBlock(blocks, 0, -1)).toBe(blocks);
    expect(moveBlock(blocks, 1, 1)).toBe(blocks);
  });
});

describe('server errors', () => {
  it("go to the block they name; the rest stay general", () => {
    const { general, byBlock } = errorsByBlock(
      ['chart_1: point 9 is not on this site', 'chart_1: point 8 is not on this site', 'nope: x', 'The report window is longer than 92 days'],
      ['chart_1', 'text_1'],
    );
    expect(Object.fromEntries(byBlock)).toEqual({ chart_1: ['point 9 is not on this site', 'point 8 is not on this site'] });
    expect(general).toEqual(['nope: x', 'The report window is longer than 92 days']);
  });

  it("are read from backend-ot's 400 body only", () => {
    expect(validationErrors({ detail: { errors: ['a: b', 3] } })).toEqual(['a: b']);
    expect(validationErrors({ detail: 'oops' })).toEqual([]);
    expect(validationErrors(null)).toEqual([]);
  });
});

describe('runRequest', () => {
  it('sends the template when nothing changed', () => {
    expect(runRequest(structuredClone(TEMPLATE.definition), TEMPLATE, '')).toEqual({ template_id: 4, name: undefined });
  });

  it('sends the template with a custom period when only the period changed', () => {
    const window = { kind: 'rolling' as const, duration: '1W' as const };
    expect(runRequest({ ...TEMPLATE.definition, window }, TEMPLATE, 'This week')).toEqual({ template_id: 4, window, name: 'This week' });
  });

  it('sends the definition when a section changed, or without a template', () => {
    const changed: ReportDefinition = { ...TEMPLATE.definition, blocks: [...TEMPLATE.definition.blocks, newBlock('alarm_events_table', [])] };
    expect(runRequest(changed, TEMPLATE, ' ')).toEqual({ definition: changed, name: undefined });
    expect(runRequest(changed, null, 'Mine')).toEqual({ definition: changed, name: 'Mine' });
  });
});
