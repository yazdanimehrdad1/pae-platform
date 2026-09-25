import { cn } from "@/lib/utils";

interface BusBarProps {
  label?: string;
  width?: string;
  className?: string;
}

export const BusBar = ({ label, width = "w-full", className }: BusBarProps) => {
  return (
    <div className={cn("relative flex flex-col items-center justify-end", className)}>
      {label && (
        <span className="text-xs font-mono text-muted-foreground mb-1 absolute -top-5 left-1/2 -translate-x-1/2 whitespace-nowrap">
          {label}
        </span>
      )}
      <div
        className={cn(
          "h-3 rounded-full bg-gradient-to-r from-primary/80 via-primary to-primary/80 pulse-glow",
          width
        )}
        style={{
          boxShadow: "0 0 15px hsl(199 89% 48% / 0.5)",
        }}
      />
    </div>
  );
};
