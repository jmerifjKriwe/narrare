"use client";

/**
 * AuthorVoicePanel — on-demand side panel for Author Voice Profiling
 * (ANAL-007 / ADR-074).
 *
 * Renders the writer's narrative-voice profile (descriptive descriptors +
 * curated passages + advanced prose-composition metrics). On-demand like
 * VoiceDriftPanel: the writer picks 3+ chapters (default: all), clicks
 * "Analyze Voice", and the resulting profile renders here. The backend
 * auto-saves the profile to ProjectSettings.author_voice on completion
 * (ADR-074 — no separate save action needed).
 *
 * Lifecycle runs through {@link useAuthorVoice} → `useAIOperation` (ADR-043):
 * no manual AbortController, SSE streaming via the author-voice stream
 * client. The results view is extracted into `_components/` per RULE-04.
 * Follows the sibling voice-panel layout (400px wide, border-left).
 *
 * NOTE (cross-layer gap, surfaced for the coordinator): the backend
 * `AuthorVoiceServiceProtocol` exposes `get_profile` and `clear_profile`,
 * but the committed router (`router_author_voice.py`, Task 3) only exposes
 * the SSE POST endpoint. The panel therefore does NOT (a) load a stored
 * profile on mount, nor (b) offer a "Clear profile" button — both would
 * require REST routes that do not exist yet. The profile renders solely
 * from the SSE `result` event of the most recent run. Coordinator: a
 * backend follow-up is needed for these two capabilities.
 *
 * @module AuthorVoicePanel
 */

import { BookOpen, Info, Loader2, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { AnalysisPanelWrapper } from "@/components/ui/analysis-panel-wrapper";
import { useAuthorVoice } from "@/lib/hooks/useAuthorVoice";
import type { ChapterSummary } from "@/types";
import { AuthorVoiceChapterSelect } from "./_components/AuthorVoiceChapterSelect";
import { AuthorVoicePanelHeader } from "./_components/AuthorVoicePanelHeader";
import { AuthorVoiceResults } from "./_components/AuthorVoiceResults";

interface AuthorVoicePanelProps {
  /** Novel to profile (author voice is novel-scoped — ADR-074). */
  novelId: string;
  /** All chapters in the novel — drives the multi-select. */
  chapters: ChapterSummary[];
  onClose: () => void;
}

type ViewState = "idle" | "loading" | "results" | "error";

export function AuthorVoicePanel({ novelId, chapters, onClose }: AuthorVoicePanelProps) {
  const t = useTranslations("analysis");
  const tStudio = useTranslations("studio");
  const { result, error, run, isLoading, isStreaming, isComplete, isError } = useAuthorVoice();

  // Default selection: ALL chapters (matches the backend "null chapter_ids =
  // all chapters" semantic). Reset when the chapter list changes (navigation,
  // volume switch, or new chapters added).
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    () => new Set(chapters.map((c) => c.id)),
  );
  useEffect(() => {
    setSelectedIds(new Set(chapters.map((c) => c.id)));
  }, [chapters]);

  const inFlight = isLoading || isStreaming;

  const viewState: ViewState = isError
    ? "error"
    : inFlight
      ? "loading"
      : isComplete && result
        ? "results"
        : "idle";

  /**
   * When ALL chapters are selected, send null (matches backend "all chapters"
   * semantic). When a subset is selected, send the explicit ID list.
   */
  const chapterIdsArg = useMemo<string[] | null>(() => {
    if (selectedIds.size === 0) return null;
    if (selectedIds.size === chapters.length) return null;
    return Array.from(selectedIds);
  }, [selectedIds, chapters.length]);

  const handleAnalyze = () => run(novelId, chapterIdsArg);

  return (
    <div className="flex h-full w-[400px] min-w-[400px] flex-col border-l border-border bg-background">
      {/* Header */}
      <AuthorVoicePanelHeader
        viewState={viewState}
        inFlight={inFlight}
        onReanalyze={handleAnalyze}
        onClose={onClose}
        t={t}
      />

      {/* Description + AI disclaimer */}
      <div className="border-b border-border bg-muted/30 px-4 py-1.5">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="h-3.5 w-3.5 flex-shrink-0" />
          {t("authorVoice.description")}
        </p>
      </div>
      <div className="border-b border-border bg-muted/30 px-4 py-1.5">
        <p className="text-xs text-muted-foreground">{t("authorVoice.aiDisclaimer")}</p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-4 p-6">
          <AnalysisPanelWrapper phase={viewState}>
            {/* Idle — Analyze CTA + chapter multi-select */}
            {viewState === "idle" && (
              <div className="space-y-4">
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-violet-100 dark:bg-violet-900/30">
                    <BookOpen className="h-8 w-8 text-violet-500" />
                  </div>
                  <p className="mb-1 text-lg font-medium">{t("authorVoice.idleTitle")}</p>
                  <p className="mb-6 max-w-sm text-sm text-muted-foreground">
                    {t("authorVoice.idleSubtext")}
                  </p>
                  <button
                    type="button"
                    onClick={handleAnalyze}
                    disabled={chapters.length === 0}
                    className="flex items-center gap-1.5 rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700 disabled:opacity-50"
                  >
                    {t("authorVoice.analyze")}
                  </button>
                </div>
                {chapters.length > 0 && (
                  <AuthorVoiceChapterSelect
                    chapters={chapters}
                    selectedIds={selectedIds}
                    onChange={setSelectedIds}
                    t={t}
                  />
                )}
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
                <p className="mb-2 text-lg font-medium">{t("authorVoice.analyzing")}</p>
                <p className="text-sm text-muted-foreground">{t("authorVoice.analyzingSubtext")}</p>
              </div>
            )}

            {/* Error */}
            {viewState === "error" && (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
                  <Info className="h-6 w-6 text-red-500" />
                </div>
                <p className="mb-1 text-lg font-medium">{t("authorVoice.analysisFailed")}</p>
                <p className="mb-4 text-sm text-muted-foreground">
                  {error ? tStudio(error.i18nKey ?? "aiActions.errorDefault") : null}
                </p>
                <button
                  type="button"
                  onClick={handleAnalyze}
                  className="flex items-center gap-1.5 rounded-md border border-border px-4 py-2 text-sm transition-colors hover:bg-muted"
                >
                  <RefreshCw className="h-4 w-4" />
                  {t("authorVoice.retry")}
                </button>
              </div>
            )}

            {/* Results */}
            {viewState === "results" && result && <AuthorVoiceResults result={result} t={t} />}
          </AnalysisPanelWrapper>
        </div>
      </div>
    </div>
  );
}
