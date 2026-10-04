import type {
  BessConfig,
  GridConfig,
  LoadConfig,
  MeterConfig,
  PvConfig,
  SiteConfig,
  TransformerConfig,
} from '@/api/types/powerflow';

// A static single line diagram of a powerflow site, laid out top to bottom the way powerflow
// builds its network (powerflow network/topology.py):
//
//   utility source ─ grid equivalent ─ (POI line) ─ POI meter ─ POI bus
//   POI bus ─ loads on the POI (optional transformer)
//   POI bus ─ feeder line or closed switch ─ collector bus
//   collector bus ─ (feeder meter) ─ step-up transformer ─ LV bus ─ BESS / PV / load
//
// Pure: config in, shapes with coordinates out. SimulationSld.tsx only draws them.

export type SldShapeKind =
  | 'source'
  | 'impedance'
  | 'line'
  | 'switch'
  | 'meter'
  | 'bus'
  | 'transformer'
  | 'bess'
  | 'pv'
  | 'load';

export interface SldShape {
  id: string;
  kind: SldShapeKind;
  x: number; // centre (a bus: its left end)
  y: number; // centre
  width: number; // a bus: its length
  height: number;
  label: string;
  details: string[];
}

export interface SldLink {
  from: [number, number];
  to: [number, number];
}

export interface SldLayout {
  shapes: SldShape[];
  links: SldLink[];
  width: number;
  height: number;
}

export const COLUMN_WIDTH = 210;
const MARGIN_X = 40;
const ROW = 92;
const ASSET_BOX = { width: 180, height: 76 };
const DEVICE_BOX = { width: 44, height: 44 };
const SMALL_BOX = { width: 60, height: 30 };

type Asset =
  | { kind: 'bess'; config: BessConfig }
  | { kind: 'pv'; config: PvConfig }
  | { kind: 'load'; config: LoadConfig };

const kw = (value: number) => `${Math.round(value).toLocaleString()} kW`;

function transformerDetails(transformer: TransformerConfig): string[] {
  return [
    `${Math.round(transformer.s_rated_kva).toLocaleString()} kVA`,
    `${transformer.vn_hv_kv}/${transformer.vn_lv_kv} kV · ${transformer.z_pct}%Z`,
  ];
}

function assetLabel(asset: Asset): string {
  return asset.config.name ?? asset.config.id;
}

function assetDetails(asset: Asset): string[] {
  switch (asset.kind) {
    case 'bess': {
      const { inverter, battery } = asset.config;
      return [
        `${Math.round(inverter.s_rated_kva).toLocaleString()} kVA · ±${kw(inverter.p_discharge_max_kw)}`,
        `${Math.round(battery.capacity_kwh).toLocaleString()} kWh · SoC ${battery.soc_min_pct ?? 5}–${battery.soc_max_pct ?? 95}%`,
      ];
    }
    case 'pv': {
      const { inverter, availability, dc_kwp } = asset.config;
      return [
        `${Math.round(inverter.s_rated_kva).toLocaleString()} kVA · ${kw(inverter.p_max_kw)}`,
        `${Math.round(dc_kwp).toLocaleString()} kWp · ${availability.scenario}`,
      ];
    }
    case 'load': {
      const { profile } = asset.config;
      return [`profile ${profile.scenario} ×${profile.scale ?? 1}`];
    }
  }
}

function transformerOf(asset: Asset): TransformerConfig | null {
  return asset.config.transformer ?? null;
}

function lvKv(asset: Asset, transformer: TransformerConfig | null): number | null {
  if (asset.kind === 'load') return transformer ? transformer.vn_lv_kv : null;
  return asset.config.inverter.v_lv_kv ?? transformer?.vn_lv_kv ?? null;
}

/** Shapes and links for a site, sized to its asset count. */
export function layoutSite(config: SiteConfig): SldLayout {
  const grid: Partial<GridConfig> = config.grid ?? {};
  const gridKv = grid.vn_kv ?? 12.47;
  const collectors = config.collectors?.length ? config.collectors : [{ id: 'mv1' }];
  const meters = new Map<string, MeterConfig>((config.meters ?? []).map((meter) => [meter.transformer, meter]));
  const poiLoads: Asset[] = (config.loads ?? [])
    .filter((load) => (load.bus ?? 'poi') === 'poi')
    .map((load) => ({ kind: 'load', config: load }));
  const assetsOf = (collectorId: string): Asset[] => [
    ...(config.bess ?? [])
      .filter((bess) => (bess.collector ?? 'mv1') === collectorId)
      .map((bess): Asset => ({ kind: 'bess', config: bess })),
    ...(config.pv ?? [])
      .filter((pv) => (pv.collector ?? 'mv1') === collectorId)
      .map((pv): Asset => ({ kind: 'pv', config: pv })),
    ...(config.loads ?? [])
      .filter((load) => load.bus === collectorId)
      .map((load): Asset => ({ kind: 'load', config: load })),
  ];
  const groups = collectors.map((collector) => ({ collector, assets: assetsOf(collector.id) }));
  const columns = poiLoads.length + groups.reduce((sum, group) => sum + Math.max(group.assets.length, 1), 0);
  const width = MARGIN_X * 2 + Math.max(columns, 2) * COLUMN_WIDTH;
  const centre = width / 2;

  const shapes: SldShape[] = [];
  const links: SldLink[] = [];
  const add = (shape: SldShape) => {
    shapes.push(shape);
    return shape;
  };
  const link = (x1: number, y1: number, x2: number, y2: number) => links.push({ from: [x1, y1], to: [x2, y2] });

  // Utility side, down the centre.
  let y = 50;
  add({
    id: 'source', kind: 'source', x: centre, y, ...DEVICE_BOX, label: 'Utility',
    details: [`${gridKv} kV`, `Ssc ${grid.sc_mva ?? 100} MVA · X/R ${grid.x_r ?? 5}`],
  });
  const chain: SldShape[] = [shapes[0]];
  y += ROW;
  chain.push(add({ id: 'grid_equivalent', kind: 'impedance', x: centre, y, ...SMALL_BOX, label: 'Grid equivalent', details: ['Z = V²/Ssc'] }));
  if (config.poi?.line) {
    y += ROW;
    const line = config.poi.line;
    chain.push(add({
      id: 'poi_line', kind: 'line', x: centre, y, ...SMALL_BOX, label: 'POI line',
      details: [`${line.length_km} km · ${line.r_ohm_per_km}+j${line.x_ohm_per_km} Ω/km`],
    }));
  }
  y += ROW;
  chain.push(add({ id: 'poi_meter', kind: 'meter', x: centre, y, ...DEVICE_BOX, label: 'POI meter', details: ['+ = export'] }));
  chain.slice(1).forEach((shape, index) => link(centre, chain[index].y + chain[index].height / 2, centre, shape.y - shape.height / 2));

  // POI bus across every column.
  y += ROW * 0.75;
  const poiBusY = y;
  const busLeft = MARGIN_X + COLUMN_WIDTH / 2 - 40;
  const busRight = width - MARGIN_X - COLUMN_WIDTH / 2 + 40;
  add({ id: 'bus:poi', kind: 'bus', x: busLeft, y: poiBusY, width: busRight - busLeft, height: 6, label: `POI ${gridKv} kV`, details: [] });
  link(centre, chain[chain.length - 1].y + DEVICE_BOX.height / 2, centre, poiBusY);

  const tieY = poiBusY + ROW * 0.8;
  const collectorBusY = tieY + ROW * 0.8;
  // Rows below a bus: feeder meter, transformer (meter row + ROW), its LV bus, the asset box.
  const meterY = collectorBusY + ROW * 0.75;
  const assetY = meterY + ROW + ROW * 0.75 + ROW * 0.85;

  // One asset column: (meter) → (transformer → LV bus) → asset box, hanging from busY.
  const drawAsset = (asset: Asset, x: number, busY: number, startY: number) => {
    const transformer = transformerOf(asset);
    const meter = meters.get(asset.config.id);
    let top = busY;
    let rowY = startY;
    if (meter) {
      const shape = add({ id: `meter:${meter.id}`, kind: 'meter', x, y: rowY, ...DEVICE_BOX, label: meter.name ?? meter.id, details: ['+ = toward bus'] });
      link(x, top, x, shape.y - shape.height / 2);
      top = shape.y + shape.height / 2;
    }
    rowY += ROW;
    if (transformer) {
      const shape = add({ id: `tx:${asset.config.id}`, kind: 'transformer', x, y: rowY, ...DEVICE_BOX, label: `tx:${asset.config.id}`, details: transformerDetails(transformer) });
      link(x, top, x, shape.y - shape.height / 2);
      const kv = lvKv(asset, transformer);
      const lvY = rowY + ROW * 0.75;
      add({ id: `bus:lv:${asset.config.id}`, kind: 'bus', x: x - 50, y: lvY, width: 100, height: 4, label: kv ? `${kv} kV` : 'LV', details: [] });
      link(x, shape.y + shape.height / 2, x, lvY);
      top = lvY;
    }
    const box = add({ id: `${asset.kind}:${asset.config.id}`, kind: asset.kind, x, y: assetY, ...ASSET_BOX, label: assetLabel(asset), details: assetDetails(asset) });
    link(x, top, x, box.y - box.height / 2);
  };

  let column = 0;
  const columnX = (index: number) => MARGIN_X + COLUMN_WIDTH * (index + 0.5);

  for (const load of poiLoads) {
    drawAsset(load, columnX(column), poiBusY, meterY);
    column += 1;
  }

  for (const { collector, assets } of groups) {
    const span = Math.max(assets.length, 1);
    const firstX = columnX(column);
    const lastX = columnX(column + span - 1);
    const midX = (firstX + lastX) / 2;
    const feeder = collector.feeder;
    const tie = add(
      feeder
        ? {
            id: `feeder:${collector.id}`, kind: 'line', x: midX, y: tieY, ...SMALL_BOX, label: `feeder:${collector.id}`,
            details: [`${feeder.length_km} km`],
          }
        : { id: `sw:${collector.id}`, kind: 'switch', x: midX, y: tieY, ...SMALL_BOX, label: `sw:${collector.id}`, details: ['closed'] },
    );
    link(midX, poiBusY, midX, tie.y - tie.height / 2);
    add({
      id: `bus:col:${collector.id}`, kind: 'bus', x: firstX - 70, y: collectorBusY, width: lastX - firstX + 140, height: 6,
      label: `${collector.id} ${gridKv} kV`, details: [],
    });
    link(midX, tie.y + tie.height / 2, midX, collectorBusY);
    assets.forEach((asset, index) => drawAsset(asset, columnX(column + index), collectorBusY, meterY));
    column += span;
  }

  return { shapes, links, width, height: assetY + ASSET_BOX.height / 2 + 30 };
}
