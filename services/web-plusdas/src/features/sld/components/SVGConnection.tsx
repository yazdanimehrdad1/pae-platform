import { useMemo, useState, useEffect } from "react";
import { cn } from "@/lib/utils";

interface SVGConnectionProps {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  flowDirection?: "down" | "up" | "left" | "right";
  powerFlowDirection?: "export" | "import" | "generate" | "consume" | "charge" | "discharge";
  className?: string;
}

export const SVGConnection = ({
  x1,
  y1,
  x2,
  y2,
  flowDirection = "down",
  powerFlowDirection,
  className,
}: SVGConnectionProps) => {
  const connectionData = useMemo(() => {
    if (!isFinite(x1) || !isFinite(y1) || !isFinite(x2) || !isFinite(y2)) {
      return null;
    }

    const minX = Math.min(x1, x2) - 20;
    const minY = Math.min(y1, y2) - 20;
    const width = Math.abs(x2 - x1) + 40;
    const height = Math.abs(y2 - y1) + 40;

    if (width <= 0 || height <= 0 || !isFinite(width) || !isFinite(height)) {
      return null;
    }

    const lineX1 = x1 - minX;
    const lineY1 = y1 - minY;
    const lineX2 = x2 - minX;
    const lineY2 = y2 - minY;

    const isReversed = flowDirection === "up" || flowDirection === "left";
    const pathD = isReversed
      ? `M ${lineX2},${lineY2} L ${lineX1},${lineY1}`
      : `M ${lineX1},${lineY1} L ${lineX2},${lineY2}`;

    const uniqueId = `conn-${Math.round(x1)}-${Math.round(y1)}-${Math.round(x2)}-${Math.round(y2)}`;
    const pathId = `path-${uniqueId}`;

    return { minX, minY, width, height, lineX1, lineY1, lineX2, lineY2, pathD, pathId, uniqueId, isReversed };
  }, [x1, y1, x2, y2, flowDirection]);

  // Hooks run on every render, before the early return below (rules of hooks).
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    setIsReady(false);
    const timer = setTimeout(() => setIsReady(true), 300);
    return () => clearTimeout(timer);
  }, [x1, y1, x2, y2]);

  if (!connectionData) return null;

  const { minX, minY, width, height, lineX1, lineY1, lineX2, lineY2, pathD, pathId } = connectionData;

  const isGeneration = powerFlowDirection === "export" ||
                       powerFlowDirection === "generate" ||
                       powerFlowDirection === "discharge";
  const dotColor = isGeneration ? "#22c55e" : "#ef4444";

  const svgKey = `svg-${Math.round(x1)}-${Math.round(y1)}-${Math.round(x2)}-${Math.round(y2)}`;

  return (
    <svg
      key={svgKey}
      className={cn("absolute pointer-events-none", className)}
      style={{
        left: `${minX}px`,
        top: `${minY}px`,
        width: `${width}px`,
        height: `${height}px`,
        overflow: "visible",
      }}
      viewBox={`0 0 ${width} ${height}`}
    >
      <defs>
        <path id={pathId} d={pathD} fill="none" />
      </defs>
      <line
        x1={lineX1}
        y1={lineY1}
        x2={lineX2}
        y2={lineY2}
        stroke="hsl(199 89% 48% / 0.4)"
        strokeWidth="4"
        strokeLinecap="round"
      />
      {isReady && (
        <circle
          key={`dot-${pathId}`}
          r="5"
          fill={dotColor}
          style={{ filter: `drop-shadow(0 0 3px ${dotColor})` }}
        >
          <animateMotion dur="5s" repeatCount="indefinite" path={pathD} rotate="auto" />
        </circle>
      )}
    </svg>
  );
};
