"use client";

/**
 * UnblockPanel — Writer's Unblock (WRITE-009).
 *
 * Renders an "Unblock" button that opens a panel offering story-direction
 * suggestions. The user may describe what they are stuck on, request 3-5
 * suggestions via SSE, then accept, dismiss, or regenerate them.
 *
 * State and lifecycle are extracted: {@link useUnblockPanel} owns the open/close
 * + interaction state and effects; {@link useUnblockStream} (via
 * {@link useAIOperation}, ADR-043) owns the SSE lifecycle — no manual
 * AbortController. §16 compliance: `studio.unblock.*` / `studio.aiActions.*`
 * labels, actionable error messages, connection-loss banner.
 *
 * `studio.unblock.*` does not define dedicated dismiss/regenerate keys, so
 * those reuse the shared `studio.aiActions.*` labels (reject / newSuggestions)
 * per the shared-label convention used across AI review surfaces.
 *
 * The render sub-sections (header, input form, results) are extracted into
 * {@link UnblockPanelHeader}, {@link UnblockInputForm} and {@link UnblockResults}
 * to keep this module under the file-size limit (RULE-04 / RULE-06).
 *
 * @module UnblockPanel
 */

import { AlertTriangle, Loader2, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { ConnectionLostBanner } from "@/components/ui/connection-lost-banner";
import type { StorySuggestion } from "@/lib/api/story-suggest-stream";
import { UnblockInputForm } from "./UnblockInputForm";
import { UnblockPanelHeader } from "./UnblockPanelHeader";
import { UnblockResults } from "./UnblockResults";
import { useUnblockPanel } from "./useUnblockPanel";

interface UnblockPanelProps {
  /** Novel to generate suggestions for (SSE URL path parameter). */
  readonly novelId: string;
  /** Optional chapter to scope the suggestions (request body). */
  readonly chapterId?: string;
  /** Called when the user accepts a suggestion (parent applies it). */
  readonly onAccept: (suggestion: StorySuggestion) => void;
}

export function UnblockPanel({ novelId, chapterId, onAccept }: UnblockPanelProps) {
  const t = useTranslations("studio");

  const {
    isOpen,
    textareaRef,
    stuckText,
    setStuckText,
    handleOpen,
    handleClose,
    handleGetSuggestions,
    handleDismiss,
    suggestions,
    error,
    isBusy,
    isConnectionLost,
    cancelSuggestions,
    retrySuggestions,
    isIdle,
    isComplete,
    isError,
  } = useUnblockPanel(novelId, chapterId);

  const errorMessage = error
    ? t((error.i18nKey ?? "unblock.error") as Parameters<typeof t>[0])
    : "";

  // -- Render: closed (trigger button) --

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={handleOpen}
        className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm transition-colors hover:bg-muted"
      >
        <Sparkles className="h-4 w-4 text-primary" />
        {t("unblock.button")}
      </button>
    );
  }

  // -- Render: open panel --

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="unblock-panel-title"
      aria-busy={isBusy}
      className="flex h-full w-[400px] min-w-[400px] flex-col border-l border-border bg-background"
    >
      <UnblockPanelHeader onClose={handleClose} t={t} />

      {isConnectionLost ? (
        <div className="p-4 pb-0">
          <ConnectionLostBanner onRetry={retrySuggestions} />
        </div>
      ) : null}

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-4 p-6">
          {/* Input form — idle only (also re-shown after Dismiss). */}
          {isIdle ? (
            <UnblockInputForm
              textareaRef={textareaRef}
              stuckText={stuckText}
              onStuckTextChange={setStuckText}
              onGetSuggestions={handleGetSuggestions}
              t={t}
            />
          ) : null}

          {/* Loading / streaming */}
          {isBusy ? (
            <div role="status" aria-live="polite" className="flex flex-col gap-3">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>{t("unblock.loading")}</span>
              </div>
              <button
                type="button"
                onClick={cancelSuggestions}
                className="inline-flex w-fit items-center rounded-md border border-border px-3 py-1.5 text-sm transition-colors hover:bg-muted"
              >
                {t("aiActions.stop")}
              </button>
            </div>
          ) : null}

          {/* Error */}
          {isError ? (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm dark:border-red-800 dark:bg-red-950/20"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500" />
              <div>
                <p className="font-medium text-red-700 dark:text-red-400">{errorMessage}</p>
                <button
                  type="button"
                  onClick={retrySuggestions}
                  className="mt-1 text-red-600 underline hover:no-underline dark:text-red-400"
                >
                  {t("aiActions.retry")}
                </button>
              </div>
            </div>
          ) : null}

          {/* Results */}
          {isComplete && suggestions ? (
            <UnblockResults
              suggestions={suggestions}
              onAccept={onAccept}
              onDismiss={handleDismiss}
              onRegenerate={handleGetSuggestions}
              t={t}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
