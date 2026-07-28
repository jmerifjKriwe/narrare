"use client";

/**
 * AuthorVoiceDriftPanel — on-demand side panel for Author Voice Drift
 * (ANAL-009 Phase 2B / ADR-073 D5 applied to ADR-074 author voice).
 *
 * Renders the SINGLE narrator drift trend (sparkline + jump markers + overall
 * classification badge + agent reasoning + per-chapter notes) — the author-
 * voice analogue of Phase 1's VoiceDriftPanel, but simpler: the author is one
 * narrator (one trend line, not a multi-character heatmap).
 *
 * On-demand (like VoiceDriftPanel): the user clicks "Analyze" to run the
 * whole-novel analysis. The drift trend + jumps + agent classification render
 * here only — NO inline editor decorations (read-only analysis, ADR-073 D5).
 *
 * Lifecycle runs through {@link useAuthorVoiceDrift} → `useAIOperation`
 * (ADR-043): no manual AbortController, SSE streaming via the author-voice-
 * drift stream client. The trend + notes are extracted into `_components/` per
 * RULE-04. Follows the sibling voice-panel layout (400px wide, border-left).
 *
 * @module AuthorVoiceDriftPanel
 */

import { ArrowLeft, Info, Loader2, PenLine, RefreshCw, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { AnalysisPanelWrapper } from "@/components/ui/analysis-panel-wrapper";
import { useAuthorVoiceDrift } from "@/lib/hooks/useAuthorVoiceDrift";
import { AuthorVoiceDriftResults } from "./_components/AuthorVoiceDriftResults";

interface AuthorVoiceDriftPanelProps {
  /** Novel to analyse (whole-novel longitudinal scope — ADR-073 Decision 5). */
  novelId: string;
  onClose: () => void;
}

type ViewState = "idle" | "loading" | "results" | "error";

export function AuthorVoiceDriftPanel({ novelId, onClose }: AuthorVoiceDriftPanelProps) {
  const t = useTranslations("analysis");
  const { result, noProfile, error, progress, run, isLoading, isStreaming, isComplete, isError } =
    useAuthorVoiceDrift();

  const inFlight = isLoading || isStreaming;

  const viewState: ViewState = isError
    ? "error"
    : inFlight
      ? "loading"
      : isComplete && (result || noProfile)
        ? "results"
        : "idle";

  const handleRun = () => run(novelId);

  return (
    <div className="flex h-full w-[400px] min-w-[400px] flex-col border-l border-border bg-background">
      {/* Header */}
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
            <h3 className="truncate font-medium">{t("authorVoiceDrift.title")}</h3>
          </div>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          {viewState === "results" && (
            <button
              type="button"
              onClick={handleRun}
              disabled={inFlight}
              className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs transition-colors hover:bg-muted disabled:opacity-50"
              aria-label={t("refresh")}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${inFlight ? "animate-spin" : ""}`} />
              {t("refresh")}
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

      {/* Description + AI disclaimer */}
      <div className="border-b border-border bg-muted/30 px-4 py-1.5">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="h-3.5 w-3.5 flex-shrink-0" />
          {t("authorVoiceDrift.description")}
        </p>
      </div>
      <div className="border-b border-border bg-muted/30 px-4 py-1.5">
        <p className="text-xs text-muted-foreground">{t("authorVoiceDrift.aiDisclaimer")}</p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-4 p-6">
          <AnalysisPanelWrapper phase={viewState}>
            {/* Idle — Analyze CTA */}
            {viewState === "idle" && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-violet-100 dark:bg-violet-900/30">
                  <PenLine className="h-8 w-8 text-violet-500" />
                </div>
                <p className="mb-1 text-lg font-medium">{t("authorVoiceDrift.idleTitle")}</p>
                <p className="mb-6 max-w-sm text-sm text-muted-foreground">
                  {t("authorVoiceDrift.idleSubtext")}
                </p>
                <button
                  type="button"
                  onClick={handleRun}
                  className="flex items-center gap-1.5 rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700"
                >
                  {t("authorVoiceDrift.analyze")}
                </button>
              </div>
            )}

            {/* Loading */}
            {viewState === "loading" && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="relative mb-6">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-violet-100 dark:bg-violet-900/30">
                    <Loader2 className="h-8 w-8 animate-spin text-violet-500" />
                  </div>
                </div>
                <p className="mb-2 text-lg font-medium">{t("authorVoiceDrift.analyzing")}</p>
                <p className="text-sm text-muted-foreground">
                  {progress ?? t("authorVoiceDrift.analyzingSubtext")}
                </p>
              </div>
            )}

            {/* Error */}
            {viewState === "error" && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
                  <Info className="h-6 w-6 text-red-500" />
                </div>
                <p className="mb-1 text-lg font-medium">{t("authorVoiceDrift.analysisFailed")}</p>
                <p className="mb-4 text-sm text-muted-foreground">{error?.userMessage}</p>
                <button
                  type="button"
                  onClick={handleRun}
                  className="flex items-center gap-1.5 rounded-md border border-border px-4 py-2 text-sm transition-colors hover:bg-muted"
                >
                  <RefreshCw className="h-4 w-4" />
                  {t("authorVoiceDrift.retry")}
                </button>
              </div>
            )}

            {/* Results (single narrator trend OR graceful no-profile skip) */}
            {viewState === "results" && (
              <AuthorVoiceDriftResults result={result} noProfile={noProfile} t={t} />
            )}
          </AnalysisPanelWrapper>
        </div>
      </div>
    </div>
  );
}
