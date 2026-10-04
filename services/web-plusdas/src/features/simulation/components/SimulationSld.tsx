import { useMemo } from "react";
import type { SiteConfig } from "@/api/types/powerflow";
import { layoutSite, type SldLive, type SldShape } from "../lib/sldLayout";

// Single line diagram of a powerflow site: names and ratings, plus (for the active site) the live
// breaker positions, faults, offline assets and comm loss. Draws the shapes laid out by
// lib/sldLayout.ts; theme colours come from the Tailwind tokens, so it works in light and dark
// mode. With onToggleBreaker, clicking a breaker opens or closes it.

type ToggleBreaker = (id: string, close: boolean) => void;

const ASSET_ACCENT: Record<string, string> = {
  bess: "stroke-emerald-500",
  pv: "stroke-amber-500",
  load: "stroke-sky-500",
};

function Tooltip({ shape }: { shape: SldShape }) {
  return <title>{[shape.label, ...shape.details].join("\n")}</title>;
}

function SideLabel({ shape }: { shape: SldShape }) {
  const x = shape.x + shape.width / 2 + 10;
  return (
    <text x={x} y={shape.y - (shape.details.length * 7)} className="fill-foreground text-[12px]">
      <tspan x={x} className="font-semibold">{shape.label}</tspan>
      {shape.details.map((detail) => (
        <tspan key={detail} x={x} dy={14} className="fill-muted-foreground text-[11px]">
          {detail}
        </tspan>
      ))}
    </text>
  );
}

function Flags({ shape }: { shape: SldShape }) {
  if (!shape.flags?.length) return null;
  return (
    <text x={shape.x + shape.width / 2 - 6} y={shape.y - shape.height / 2 - 6} textAnchor="end" className="fill-destructive text-[11px] font-semibold">
      {shape.flags.join(" · ")}
    </text>
  );
}

function Breaker({ shape, onToggle }: { shape: SldShape; onToggle?: ToggleBreaker }) {
  const { x, y, width, height } = shape;
  const closed = shape.breaker?.closed ?? true;
  const id = shape.breaker?.id ?? "";
  const toggle = onToggle ? () => onToggle(id, !closed) : undefined;
  return (
    <g
      data-shape={shape.id}
      data-breaker={closed ? "closed" : "open"}
      role={toggle ? "button" : undefined}
      tabIndex={toggle ? 0 : undefined}
      aria-label={toggle ? `${closed ? "Open" : "Close"} breaker ${id}` : undefined}
      className={toggle ? "cursor-pointer" : undefined}
      onClick={toggle}
      onKeyDown={toggle ? (event) => (event.key === "Enter" || event.key === " ") && toggle() : undefined}
    >
      <rect
        x={x - width / 2}
        y={y - height / 2}
        width={width}
        height={height}
        className={closed ? "fill-foreground stroke-foreground" : "fill-card stroke-destructive"}
        strokeWidth={2}
      />
      {!closed && (
        <line x1={x - width / 2} y1={y + height / 2} x2={x + width / 2} y2={y - height / 2} className="stroke-destructive" strokeWidth={2} />
      )}
      <title>{`${shape.label}: ${closed ? "closed" : "open"}${toggle ? " (click to switch)" : ""}`}</title>
    </g>
  );
}

function Shape({ shape, onToggleBreaker }: { shape: SldShape; onToggleBreaker?: ToggleBreaker }) {
  const { x, y, width, height } = shape;
  const left = x - width / 2;
  const top = y - height / 2;
  switch (shape.kind) {
    case "bus":
      return (
        <g data-shape={shape.id}>
          <rect x={x} y={y - height / 2} width={width} height={height} rx={2} className="fill-foreground" />
          <text x={x} y={y - 8} className="fill-muted-foreground text-[11px]">{shape.label}</text>
          <Tooltip shape={shape} />
        </g>
      );
    case "source":
      return (
        <g data-shape={shape.id}>
          <circle cx={x} cy={y} r={width / 2} className="fill-card stroke-foreground" strokeWidth={2} />
          <text x={x} y={y + 5} textAnchor="middle" className="fill-foreground text-[18px]">~</text>
          <SideLabel shape={shape} />
          <Tooltip shape={shape} />
        </g>
      );
    case "breaker":
      return <Breaker shape={shape} onToggle={onToggleBreaker} />;
    case "meter":
      return (
        <g data-shape={shape.id} data-flags={shape.flags?.join(",") || undefined}>
          <Flags shape={shape} />
          <circle cx={x} cy={y} r={width / 2 - 6} className="fill-card stroke-primary" strokeWidth={2} />
          <text x={x} y={y + 5} textAnchor="middle" className="fill-primary text-[14px] font-semibold">M</text>
          <SideLabel shape={shape} />
          <Tooltip shape={shape} />
        </g>
      );
    case "transformer":
      return (
        <g data-shape={shape.id}>
          <circle cx={x} cy={y - 8} r={12} className="fill-none stroke-foreground" strokeWidth={2} />
          <circle cx={x} cy={y + 8} r={12} className="fill-none stroke-foreground" strokeWidth={2} />
          <SideLabel shape={shape} />
          <Tooltip shape={shape} />
        </g>
      );
    case "impedance":
    case "line":
    case "switch":
      return (
        <g data-shape={shape.id}>
          <rect x={left} y={top} width={width} height={height} rx={4} className="fill-card stroke-foreground" strokeWidth={1.5} />
          <text x={x} y={y + 4} textAnchor="middle" className="fill-foreground text-[11px]">
            {shape.kind === "impedance" ? "Z" : shape.kind === "switch" ? "switch" : "line"}
          </text>
          <SideLabel shape={shape} />
          <Tooltip shape={shape} />
        </g>
      );
    case "bess":
    case "pv":
    case "load": {
      const faulted = shape.flags?.includes("fault");
      const offline = shape.flags?.includes("offline");
      return (
        <g data-shape={shape.id} data-flags={shape.flags?.join(",") || undefined} opacity={offline ? 0.5 : 1}>
          <rect
            x={left}
            y={top}
            width={width}
            height={height}
            rx={8}
            className={`fill-card ${faulted ? "stroke-destructive" : ASSET_ACCENT[shape.kind]}`}
            strokeWidth={faulted ? 3 : 2}
            strokeDasharray={offline ? "6 4" : undefined}
          />
          <Flags shape={shape} />
          <text x={left + 10} y={top + 20} className="fill-foreground text-[13px] font-semibold">
            {shape.kind.toUpperCase()} · {shape.label}
          </text>
          {shape.details.map((detail, index) => (
            <text key={detail} x={left + 10} y={top + 40 + index * 16} className="fill-muted-foreground text-[11px]">
              {detail}
            </text>
          ))}
          <Tooltip shape={shape} />
        </g>
      );
    }
  }
}

export function SimulationSld({
  config,
  live,
  onToggleBreaker,
}: {
  config: SiteConfig;
  live?: SldLive;
  onToggleBreaker?: ToggleBreaker;
}) {
  const layout = useMemo(() => layoutSite(config, live), [config, live]);
  return (
    <div className="w-full overflow-x-auto">
      <svg
        data-simulation-sld
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        className="w-full min-w-[640px]"
        style={{ maxHeight: 900 }}
        role="img"
        aria-label={`Single line diagram of ${config.site?.name ?? "the site"}`}
      >
        {layout.links.map((link, index) => (
          <line
            key={index}
            x1={link.from[0]}
            y1={link.from[1]}
            x2={link.to[0]}
            y2={link.to[1]}
            className="stroke-muted-foreground"
            strokeWidth={2}
          />
        ))}
        {layout.shapes.map((shape) => (
          <Shape key={shape.id} shape={shape} onToggleBreaker={onToggleBreaker} />
        ))}
      </svg>
    </div>
  );
}
