"use client";

/**
 * SentimentPanel — collapsible side panel for Sentiment Analysis (ANAL-002).
 *
 * Owns state management, analysis lifecycle, and error handling.
 * Delegates rendering to extracted sub-components.
 * Follows BetaReaderPanel layout (400px wide, border-left).
 */

import { Info, Loader2, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import type { SentimentOverview } from "@/lib/api/analysis";
import { useSentimentAnalyze } from "@/lib/hooks/useSentiment";
import { useEditorStore } from "@/lib/stores/editorStore";
import { SentimentPanelHeader } from "./_components/SentimentPanelHeader";
import { SentimentResults } from "./_components/SentimentResults";

// --- Types ---

interface SentimentPanelProps {
  novelId: string;
  chapterIds: string[];
  onClose: () => void;
}

// --- Component ---

export function SentimentPanel({ novelId, chapterIds, onClose }: SentimentPanelProps) {
  const t = useTranslations("analysis");

  const [viewState, setViewState] = useState<"idle" | "loading" | "results" | "error">("idle");
  const [results, setResults] = useState<SentimentOverview[] | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [activeChapterIdx, setActiveChapterIdx] = useState(0);

  const analyzeMutation = useSentimentAnalyze(novelId);
  const setSentimentResult = useEditorStore((s) => s.setSentimentResult);
  const setSentimentLoading = useEditorStore((s) => s.setSentimentLoading);

  // --- Run analysis ---

  const runAnalysis = useCallback(
    // Parameter kept for consistent API with BetaReaderPanel refresh pattern.
    // Sentiment analysis is deterministic — refresh always returns fresh data.
    async (_refresh = false) => {
      if (chapterIds.length === 0) return;
      setViewState("loading");
      setSentimentLoading(true);
      setError(null);

      try {
        const res = await analyzeMutation.mutateAsync({
          chapter_ids: chapterIds,
          detect_arc: true,
        });
        setResults(res);
        setSentimentResult(res);
        setViewState("results");
        setActiveChapterIdx(0);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setViewState("error");
      } finally {
        setSentimentLoading(false);
      }
    },
    [chapterIds, analyzeMutation, setSentimentResult, setSentimentLoading],
  );

  // Auto-trigger on mount
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount
  useEffect(() => {
    if (viewState !== "idle") return;
    void runAnalysis(false);
  }, []);

  // --- Derived ---

  const activeResult = results?.[activeChapterIdx] ?? null;

  // --- i18n adapter ---

  const tFn = (key: string, params?: Record<string, unknown>) => {
    return t(key as Parameters<typeof t>[0], params as Parameters<typeof t>[1]) as string;
  };

  // --- Render ---

  return (
    <div className="flex flex-col h-full border-l border-border bg-background w-[400px] min-w-[400px]">
      <SentimentPanelHeader
        onClose={onClose}
        showRefresh={viewState === "results"}
        isPending={analyzeMutation.isPending}
        onRefresh={() => void runAnalysis(true)}
        title={t("sentiment.title")}
        disclaimer={t("sentiment.disclaimer")}
        closeLabel={t("close")}
        refreshLabel={t("refresh")}
      />

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          {/* Loading state */}
          {viewState === "loading" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="relative mb-6">
                <div className="w-16 h-16 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                  <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                </div>
              </div>
              <p className="text-lg font-medium mb-2">{t("sentiment.loading")}</p>
              <p className="text-sm text-muted-foreground">{t("sentiment.loadingSubtext")}</p>
            </div>
          )}

          {/* Error state */}
          {viewState === "error" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
                <Info className="w-6 h-6 text-red-500" />
              </div>
              <p className="text-lg font-medium mb-1">{t("error")}</p>
              <p className="text-sm text-muted-foreground mb-4">{error?.message}</p>
              <button
                type="button"
                onClick={() => void runAnalysis(false)}
                className="flex items-center gap-1.5 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                {t("retry")}
              </button>
            </div>
          )}

          {/* Results */}
          {viewState === "results" && results && activeResult && (
            <SentimentResults
              results={results}
              activeResult={activeResult}
              activeChapterIdx={activeChapterIdx}
              onChapterSelect={setActiveChapterIdx}
              t={tFn}
            />
          )}
        </div>
      </div>
    </div>
  );
}
