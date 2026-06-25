"use client";

/**
 * UnblockPanel — Writer's Unblock (WRITE-009).
 *
 * Renders an "Unblock" button that opens a panel offering story-direction
 * suggestions. The user may describe what they are stuck on, request 3-5
 * suggestions via SSE, then accept, dismiss, or regenerate them.
 *
 * Lifecycle (loading / streaming / error / cancel / connection-lost) is managed
 * by {@link useAIOperation} (ADR-043) via the {@link useUnblockStream} hook — no
 * manual AbortController. §16 compliance: `studio.unblock.*` /
 * `studio.aiActions.*` labels, actionable error messages, connection-loss
 * banner.
 *
 * `studio.unblock.*` does not define dedicated dismiss/regenerate keys, so
 * those reuse the shared `studio.aiActions.*` labels (reject / newSuggestions)
 * per the shared-label convention used across AI review surfaces.
 *
 * @module UnblockPanel
 */

import { AlertTriangle, Lightbulb, Loader2, RefreshCw, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { ConnectionLostBanner } from "@/components/ui/connection-lost-banner";
import type { StorySuggestion } from "@/lib/api/story-suggest-stream";
import { UnblockSuggestionCard } from "./UnblockSuggestionCard";
import { useUnblockStream } from "./useUnblockStream";

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

  const [isOpen, setIsOpen] = useState(false);
  const [stuckText, setStuckText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const {
    state: aiState,
    cancel: cancelSuggestions,
    retry: retrySuggestions,
    reset: resetSuggestions,
    request: requestSuggestions,
    isIdle,
    isLoading,
    isStreaming,
    isComplete,
    isError,
    isConnectionLost,
  } = useUnblockStream(novelId, chapterId);

  const suggestions = aiState.result;
  const error = aiState.error;
  const isBusy = isLoading || isStreaming;
  const errorMessage = error
    ? t((error.i18nKey ?? "unblock.error") as Parameters<typeof t>[0])
    : "";

  // -- Handlers --

  const handleOpen = useCallback(() => setIsOpen(true), []);

  const handleClose = useCallback(() => {
    cancelSuggestions();
    setIsOpen(false);
  }, [cancelSuggestions]);

  const handleGetSuggestions = useCallback(() => {
    requestSuggestions(stuckText);
  }, [requestSuggestions, stuckText]);

  const handleDismiss = useCallback(() => {
    // Clear results, return to the input form.
    resetSuggestions();
    setStuckText("");
    textareaRef.current?.focus();
  }, [resetSuggestions]);

  // Escape closes the panel (only while open).
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        handleClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, handleClose]);

  // Focus the textarea when the panel opens.
  useEffect(() => {
    if (!isOpen) return;
    const id = window.setTimeout(() => textareaRef.current?.focus(), 0);
    return () => window.clearTimeout(id);
  }, [isOpen]);

  // Cancel any in-flight stream on unmount.
  useEffect(() => {
    return () => cancelSuggestions();
  }, [cancelSuggestions]);

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
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border bg-card p-4">
        <div className="flex items-center gap-2">
          <Lightbulb className="h-5 w-5 text-primary" />
          <h3 id="unblock-panel-title" className="font-medium">
            {t("unblock.title")}
          </h3>
        </div>
        <button
          type="button"
          onClick={handleClose}
          aria-label={t("unblock.button")}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {isConnectionLost ? (
        <div className="p-4 pb-0">
          <ConnectionLostBanner onRetry={retrySuggestions} />
        </div>
      ) : null}

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-4 p-6">
          {/* Input form — idle only (also re-shown after Dismiss). */}
          {isIdle ? (
            <div className="space-y-3">
              <label htmlFor="unblock-stuck" className="block text-sm">
                {t("unblock.stuckLabel")}
              </label>
              <textarea
                ref={textareaRef}
                id="unblock-stuck"
                value={stuckText}
                onChange={(e) => setStuckText(e.target.value)}
                rows={3}
                className="w-full rounded-lg border border-border bg-input-background px-3 py-2 text-sm"
              />
              <button
                type="button"
                onClick={handleGetSuggestions}
                className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground transition-colors hover:bg-primary/90"
              >
                <Sparkles className="h-4 w-4" />
                {t("unblock.getSuggestions")}
              </button>
            </div>
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
            suggestions.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("unblock.empty")}</p>
            ) : (
              <div className="space-y-4">
                <ul className="space-y-3">
                  {suggestions.map((suggestion, index) => (
                    <li key={`${suggestion.type}-${suggestion.title}`}>
                      <UnblockSuggestionCard
                        suggestion={suggestion}
                        index={index}
                        onAccept={onAccept}
                        t={t}
                      />
                    </li>
                  ))}
                </ul>

                <div className="flex items-center gap-2 border-t border-border pt-3">
                  <button
                    type="button"
                    onClick={handleDismiss}
                    className="rounded-md border border-border px-3 py-1.5 text-sm transition-colors hover:bg-muted"
                  >
                    {t("aiActions.reject")}
                  </button>
                  <button
                    type="button"
                    onClick={handleGetSuggestions}
                    className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm transition-colors hover:bg-muted"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    {t("aiActions.newSuggestions")}
                  </button>
                </div>
              </div>
            )
          ) : null}
        </div>
      </div>
    </div>
  );
}
