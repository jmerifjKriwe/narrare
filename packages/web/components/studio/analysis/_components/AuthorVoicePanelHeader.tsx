"use client";

/**
 * AuthorVoicePanelHeader — top bar of {@link AuthorVoicePanel} (ANAL-007).
 *
 * Extracted per RULE-04: the panel exceeded the 200-line component limit, and
 * the header is a self-contained UI region (title, back/close actions,
 * re-analyze control). Behavior-preserving — the JSX is identical to the
 * inline original; the panel still owns the lifecycle (viewState / inFlight /
 * handlers) and threads them here as props.
 *
 * @module AuthorVoicePanelHeader
 */

import { ArrowLeft, PenLine, RefreshCw, X } from "lucide-react";

/** next-intl translation function (mirrors AuthorVoiceChapterSelect's `t`). */
type TranslationFunc = (key: string, values?: Record<string, string | number | Date>) => string;

export interface AuthorVoicePanelHeaderProps {
  /** Current panel view — only "results" shows the re-analyze control. */
  viewState: "idle" | "loading" | "results" | "error";
  /** True while a run is in flight — disables + spins the re-analyze button. */
  inFlight: boolean;
  /** Restart the analysis (re-analyze). */
  onReanalyze: () => void;
  /** Close the panel (used by both the back arrow and the X button). */
  onClose: () => void;
  t: TranslationFunc;
}

export function AuthorVoicePanelHeader({
  viewState,
  inFlight,
  onReanalyze,
  onClose,
  t,
}: AuthorVoicePanelHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-border bg-card p-4">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onClose}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label={t("close")}
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex min-w-0 items-center gap-2">
          <PenLine className="h-5 w-5 flex-shrink-0 text-violet-500" />
          <h3 className="truncate font-medium">{t("authorVoice.title")}</h3>
        </div>
      </div>
      <div className="flex flex-shrink-0 items-center gap-2">
        {viewState === "results" && (
          <button
            type="button"
            onClick={onReanalyze}
            disabled={inFlight}
            className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs transition-colors hover:bg-muted disabled:opacity-50"
            aria-label={t("authorVoice.reanalyze")}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${inFlight ? "animate-spin" : ""}`} />
            {t("authorVoice.reanalyze")}
          </button>
        )}
        <button
          type="button"
          onClick={onClose}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label={t("close")}
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
