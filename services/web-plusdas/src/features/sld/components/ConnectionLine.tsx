import { cn } from "@/lib/utils";

interface ConnectionLineProps {
  direction?: "vertical" | "horizontal";
  length?: number;
  hasFlow?: boolean;
  flowDirection?: "down" | "up" | "left" | "right";
  className?: string;
}

export const ConnectionLine = ({
  direction = "vertical",
  length = 40,
  hasFlow = true,
  flowDirection = "down",
  className,
}: ConnectionLineProps) => {
  const isVertical = direction === "vertical";

  return (
    <div
      className={cn(
        "relative flex items-center justify-center",
        isVertical ? "flex-col" : "flex-row",
        className
      )}
      style={{
        width: isVertical ? "4px" : `${length}px`,
        height: isVertical ? `${length}px` : "4px",
      }}
    >
      <div
        className={cn(
          "bg-primary/60 rounded-full",
          isVertical ? "w-0.5 h-full" : "h-0.5 w-full"
        )}
      />
      {hasFlow && (
        <div
          className={cn(
            "absolute w-2 h-2 rounded-full bg-primary",
            flowDirection === "down" && "animate-flow-down",
            flowDirection === "up" && "animate-flow-up"
          )}
          style={{
            boxShadow: "0 0 8px hsl(199 89% 48% / 0.8)",
          }}
        />
      )}
    </div>
  );
};
