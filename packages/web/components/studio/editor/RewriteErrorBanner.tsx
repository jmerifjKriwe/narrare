"use client";

/**
 * Standalone rewrite error surface (audit B01).
 *
 * The RewriteSuggestionModal renders errors only while mounted, and it
 * mounts only when an alternative has arrived (`aiSuggestion`). On a
 * pre-stream failure (e.g. a 422 before any data) the flow resets to idle
 * and the modal never opens — the error was rendered nowhere ("modal
 * closes silently"). This banner renders the structured error whenever one
 * is set and no suggestion modal is showing.
 */

import { AlertTriangle } from "lucide-react";
import type { useTranslations } from "next-intl";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";

type StudioTranslator = ReturnType<typeof useTranslations>;

interface RewriteErrorBannerProps {
  readonly error: AIErrorResponse;
  readonly onRetry: () => void;
  readonly onDismiss: () => void;
  readonly t: StudioTranslator;
}

export function RewriteErrorBanner({ error, onRetry, onDismiss, t }: RewriteErrorBannerProps) {
  return (
    <div
      role="alert"
      data-testid="rewrite-error-banner"
      className="absolute bottom-4 left-1/2 -translate-x-1/2 z-40 max-w-xl w-full mx-4 px-4 py-3 flex items-start gap-2 bg-card border border-destructive/30 rounded-lg shadow-lg text-sm"
    >
      <AlertTriangle className="w-4 h-4 text-destructive flex-shrink-0 mt-0.5" />
      <p className="flex-1 text-foreground">{resolveMessage(error, t)}</p>
      {error.retryable && (
        <button
          type="button"
          onClick={onRetry}
          className="underline hover:no-underline text-primary"
        >
          {t("aiActions.retry")}
        </button>
      )}
      <button
        type="button"
        onClick={onDismiss}
        className="underline hover:no-underline text-muted-foreground"
      >
        {t("aiActions.dismiss")}
      </button>
    </div>
  );
}

/** Resolve a structured AIErrorResponse to a user-facing message. */
function resolveMessage(error: AIErrorResponse, t: StudioTranslator): string {
  try {
    // next-intl v4 does not throw for missing messages — it renders the raw
    // key path. Detect unknown keys via `t.has` (the repo's raw-key fallback
    // pattern, see CostsBreakdownTables) so the mapper-resolved userMessage
    // takes over instead of leaking a key path into the UI.
    if (t.has(error.i18nKey as Parameters<typeof t>[0])) {
      return t(error.i18nKey as Parameters<typeof t>[0]);
    }
  } catch {
    // Defensive: translator setups that throw on unknown keys.
  }
  return error.userMessage || t("aiActions.errorDefault");
}
