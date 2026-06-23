"use client";

import type { RecoveryState } from "./createSessionMessageHandler";

interface SessionReconnectBannerProps {
  readonly recoveryState: RecoveryState;
  readonly reconnectingLabel: string;
  readonly recoveredLabel: string;
  readonly recoveryFailedLabel: string;
  readonly connectionLostLabel: string;
  readonly preserveLocalCopyLabel: string;
  readonly retryLabel: string;
  readonly localProse: string;
  readonly onRetry: () => void;
}

export function SessionReconnectBanner({
  recoveryState,
  reconnectingLabel,
  recoveredLabel,
  recoveryFailedLabel,
  connectionLostLabel,
  preserveLocalCopyLabel,
  retryLabel,
  localProse,
  onRetry,
}: SessionReconnectBannerProps) {
  if (recoveryState === "idle") return null;

  if (recoveryState === "failed") {
    return (
      <section
        aria-live="polite"
        className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-foreground"
      >
        <p className="font-medium">{recoveryFailedLabel}</p>
        <p className="mt-1 text-xs text-muted-foreground">{preserveLocalCopyLabel}</p>
        {localProse ? (
          <p className="mt-2 max-h-24 overflow-y-auto whitespace-pre-wrap rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground">
            {localProse}
          </p>
        ) : null}
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90 transition-opacity"
          aria-label={retryLabel}
        >
          {retryLabel}
        </button>
      </section>
    );
  }

  const label = recoveryState === "recovered" ? recoveredLabel : reconnectingLabel;

  return (
    <section
      aria-live="polite"
      className="rounded-lg border border-border bg-muted px-3 py-2 text-sm text-foreground"
    >
      <p className="font-medium">
        {recoveryState === "reconnecting" ? connectionLostLabel : label}
      </p>
      {recoveryState === "reconnecting" ? (
        <p className="mt-1 text-xs text-muted-foreground">{reconnectingLabel}</p>
      ) : null}
    </section>
  );
}
