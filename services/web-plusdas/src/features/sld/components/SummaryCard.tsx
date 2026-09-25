import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface SummaryCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  color?: string;
  icon?: ReactNode;
  trend?: {
    value: number;
    direction: "up" | "down" | "neutral";
  };
  className?: string;
}

export const SummaryCard = ({
  label,
  value,
  subtext,
  color,
  icon,
  trend,
  className,
}: SummaryCardProps) => {
  const trendColor =
    trend?.direction === "up"
      ? "text-success"
      : trend?.direction === "down"
      ? "text-destructive"
      : "text-muted-foreground";

  return (
    <div
      className={cn(
        "bg-background border border-border rounded-lg p-4 transition-colors hover:border-primary/50",
        className
      )}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="text-xs text-muted-foreground font-mono uppercase tracking-wider">
          {label}
        </div>
        {icon && <div className="text-muted-foreground">{icon}</div>}
      </div>
      <div className={cn("text-2xl font-semibold font-mono mb-1", color || "text-foreground")}>
        {value}
      </div>
      {subtext && (
        <div className="text-xs text-muted-foreground flex items-center gap-2">
          <span>{subtext}</span>
          {trend && (
            <span className={trendColor}>
              {trend.direction === "up" ? "↑" : trend.direction === "down" ? "↓" : "→"}{" "}
              {trend.value}%
            </span>
          )}
        </div>
      )}
    </div>
  );
};
