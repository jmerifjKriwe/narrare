import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type StatusState = "idle" | "loading" | "success" | "error" | "empty";
type Politeness = "polite" | "assertive";

interface StatusMessageProps {
  readonly state: StatusState;
  readonly message?: string;
  readonly action?: ReactNode;
  readonly politeness?: Politeness;
}

/**
 * Non-blocking loading/error/empty/success live region (spec §5.7).
 * Presentation only — callers pass resolved i18n strings and own streaming
 * (RULE-13). Errors are announced with role=alert/assertive and should carry
 * an actionable `action` (ui-principles §16.5).
 */
export function StatusMessage({ state, message, action, politeness }: StatusMessageProps) {
  const isError = state === "error";
  const live = politeness ?? (isError ? "assertive" : "polite");
  const role = isError ? "alert" : "status";
  const busy = state === "loading";

  if (state === "idle") {
    // Keep the live region mounted but empty so the next transition announces.
    return <div role="status" aria-live={live} className="sr-only" />;
  }

  return (
    <div
      role={role}
      aria-live={live}
      aria-busy={busy || undefined}
      className={cn(
        "flex items-center gap-2 rounded-md p-3 text-sm",
        isError
          ? "border border-destructive/40 bg-destructive/5 text-destructive"
          : "text-muted-foreground",
      )}
    >
      {busy && <Loader2 aria-hidden="true" className="h-4 w-4 shrink-0 animate-spin" />}
      {message && <span className="flex-1">{message}</span>}
      {action && <span className="shrink-0">{action}</span>}
    </div>
  );
}
