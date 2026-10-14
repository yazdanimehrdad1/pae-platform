import type { ReactNode } from "react";
import { CircleAlert } from "lucide-react";

/** One report section: its title, an optional action (e.g. CSV), and its content or its error. */
export function BlockSection({ title, error, action, children }: {
  title?: string | null;
  error?: string | null;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="break-inside-avoid space-y-3 rounded-lg border border-border p-4 print:border-neutral-300">
      {(title || action) && (
        <div className="flex items-center justify-between gap-3">
          {title ? <h2 className="text-lg font-semibold">{title}</h2> : <span />}
          {action && !error && <div className="print:hidden">{action}</div>}
        </div>
      )}
      {error ? (
        <p className="flex items-start gap-2 text-sm text-destructive">
          <CircleAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
          This section could not be generated: {error}
        </p>
      ) : children}
    </section>
  );
}
