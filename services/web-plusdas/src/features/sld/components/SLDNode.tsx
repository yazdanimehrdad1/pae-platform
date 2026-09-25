import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface SLDNodeProps {
  title: string;
  icon: ReactNode;
  power?: string;
  status?: "online" | "warning" | "offline";
  variant?: "grid" | "solar" | "wind" | "battery" | "load" | "transformer";
  className?: string;
  children?: ReactNode;
}

const variantStyles = {
  grid: "sld-node-grid",
  solar: "sld-node-solar",
  wind: "sld-node-wind",
  battery: "sld-node-battery",
  load: "",
  transformer: "border-muted-foreground",
};

const statusStyles = {
  online: "status-online",
  warning: "status-warning",
  offline: "status-offline",
};

export const SLDNode = ({
  title,
  icon,
  power,
  status = "online",
  variant = "load",
  className,
  children,
}: SLDNodeProps) => {
  return (
    <div
      className={cn(
        "sld-node min-w-[140px] h-[150px] flex flex-col",
        variantStyles[variant],
        className
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="text-primary">{icon}</div>
          <span className="text-sm font-medium text-foreground">{title}</span>
        </div>
        <span
          className={cn(
            "text-[10px] font-mono px-1.5 py-0.5 rounded-full uppercase tracking-wider",
            statusStyles[status]
          )}
        >
          {status}
        </span>
      </div>
      {power && (
        <div className="font-mono text-lg font-semibold text-primary mb-2">
          {power}
        </div>
      )}
      <div className="flex-1 flex flex-col justify-start">
        {children}
      </div>
    </div>
  );
};
