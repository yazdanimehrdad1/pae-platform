import { describe, expect, it } from 'vitest';
import { layoutSite, type SldShape } from '@/features/simulation/lib/sldLayout';
import { REFERENCE_SITE, TWO_COLLECTOR_SITE } from '../fixtures';

const ids = (shapes: SldShape[]) => shapes.map((shape) => shape.id);

function boxesOverlap(a: SldShape, b: SldShape): boolean {
  return (
    Math.abs(a.x - b.x) < (a.width + b.width) / 2 && Math.abs(a.y - b.y) < (a.height + b.height) / 2
  );
}

describe('layoutSite', () => {
  it('draws the utility side, the POI and every asset of the reference site', () => {
    const { shapes } = layoutSite(REFERENCE_SITE);
    expect(ids(shapes)).toEqual(
      expect.arrayContaining([
        'source', 'grid_equivalent', 'poi_line', 'poi_meter', 'bus:poi', 'sw:mv1', 'bus:col:mv1',
        'bess:bess1', 'bess:bess2', 'pv:pv1', 'load:load1',
        'tx:bess1', 'tx:bess2', 'tx:pv1',
        'meter:m_bess1', 'meter:m_bess2', 'meter:m_pv1',
      ]),
    );
    const bess = shapes.find((shape) => shape.id === 'bess:bess1')!;
    expect(bess.details.join(' ')).toContain('10,000 kWh');
    expect(shapes.find((shape) => shape.id === 'tx:pv1')!.details.join(' ')).toContain('12.47/0.48 kV');
  });

  it('draws the POI line only when configured, and a feeder or a switch per collector', () => {
    const { shapes } = layoutSite(TWO_COLLECTOR_SITE);
    expect(ids(shapes)).not.toContain('poi_line');
    expect(ids(shapes)).toEqual(expect.arrayContaining(['feeder:mv1', 'feeder:mv2', 'bus:col:mv1', 'bus:col:mv2']));
    expect(ids(shapes)).not.toContain('sw:mv1');
    // The load's own transformer is drawn; no meters configured here.
    expect(ids(shapes)).toContain('tx:load1');
    expect(shapes.some((shape) => shape.kind === 'meter' && shape.id !== 'poi_meter')).toBe(false);
  });

  it('keeps asset boxes apart and inside the diagram', () => {
    for (const site of [REFERENCE_SITE, TWO_COLLECTOR_SITE]) {
      const layout = layoutSite(site);
      const boxes = layout.shapes.filter((shape) => ['bess', 'pv', 'load'].includes(shape.kind));
      for (const [index, box] of boxes.entries()) {
        expect(box.x - box.width / 2).toBeGreaterThanOrEqual(0);
        expect(box.x + box.width / 2).toBeLessThanOrEqual(layout.width);
        for (const other of boxes.slice(index + 1)) expect(boxesOverlap(box, other)).toBe(false);
      }
    }
  });
});
