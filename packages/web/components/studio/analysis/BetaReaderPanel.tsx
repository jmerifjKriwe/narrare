"use client";

/**
 * BetaReaderPanel — collapsible analysis results panel with 4 tabs.
 *
 * Tabs: Strengths | Issues | Questions | Overall
 * Shows loading/error/empty states. "Deep Dive" button on category tabs.
 * Follows WorldbuildingAnalysisPanel patterns (RULE-04).
 * Tab content extracted to BetaReaderPanelContent.tsx.
 */

import { ArrowLeft, Info, Loader2, RefreshCw, Sparkles, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { BetaReaderResponse, FeedbackCategory } from "@/lib/api/analysis";
import { useBetaReaderAnalyze, useBetaReaderDeepDive } from "@/lib/hooks/useBetaReader";
import { useEditorStore } from "@/lib/stores/editorStore";
import {
  BetaReaderPanelContent,
  type BetaTab,
  TAB_CONFIG,
  type ViewState,
} from "./BetaReaderPanelContent";

// --- Types ---

interface BetaReaderPanelProps {
  novelId: string;
  chapterIds: string[];
  onClose: () => void;
}

// --- Component ---

export function BetaReaderPanel({ novelId, chapterIds, onClose }: BetaReaderPanelProps) {
  const t = useTranslations("analysis");

  const [viewState, setViewState] = useState<ViewState>("idle");
  const [result, setResult] = useState<BetaReaderResponse | null>(null);
  const [activeTab, setActiveTab] = useState<BetaTab>("strengths");
  const [error, setError] = useState<Error | null>(null);
  const [deepDiveCategory, setDeepDiveCategory] = useState<FeedbackCategory | null>(null);

  const analyzeMutation = useBetaReaderAnalyze(novelId);
  const deepDiveMutation = useBetaReaderDeepDive(novelId);
  const setBetaReaderResult = useEditorStore((s) => s.setBetaReaderResult);
  const setBetaReaderLoading = useEditorStore((s) => s.setBetaReaderLoading);

  // --- Run Phase 1 analysis ---

  const runAnalysis = useCallback(
    async (refresh = false) => {
      if (chapterIds.length === 0) return;
      setViewState("loading");
      setBetaReaderLoading(true);
      setError(null);

      try {
        const res = await analyzeMutation.mutateAsync({
          chapter_ids: chapterIds,
          phase: "full",
          refresh,
        });
        setResult(res);
        setBetaReaderResult(res);
        setViewState("results");
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setViewState("error");
      } finally {
        setBetaReaderLoading(false);
      }
    },
    [chapterIds, analyzeMutation, setBetaReaderResult, setBetaReaderLoading],
  );

  // Auto-trigger on mount
  // biome-ignore lint/correctness/useExhaustiveDependencies: Runs once on mount
  useEffect(() => {
    if (viewState !== "idle") return;
    void runAnalysis(false);
  }, []);

  // --- Phase 2 deep dive ---

  const handleDeepDive = useCallback(
    async (category: FeedbackCategory) => {
      if (!result) return;
      setDeepDiveCategory(category);

      try {
        await deepDiveMutation.mutateAsync({
          chapter_ids: chapterIds,
          category,
          cache_key: result.cache_key,
        });
      } finally {
        setDeepDiveCategory(null);
      }
    },
    [result, chapterIds, deepDiveMutation],
  );

  // --- Derived ---

  const isCategoryTab =
    activeTab === "strengths" || activeTab === "issues" || activeTab === "questions";

  // --- i18n adapter for extracted content ---

  const tFn = (key: string, params?: Record<string, unknown>) => {
    // Use `t` from next-intl — supports dot-notation keys
    return t(key as Parameters<typeof t>[0], params as Parameters<typeof t>[1]) as string;
  };

  // --- Render ---

  return (
    <div className="flex flex-col h-full border-l border-border bg-background w-[400px] min-w-[400px]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
            aria-label={t("close")}
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <Sparkles className="w-5 h-5 text-purple-500 flex-shrink-0" />
            <h3 className="font-medium truncate">{t("title")}</h3>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {viewState === "results" && (
            <button
              type="button"
              onClick={() => void runAnalysis(true)}
              disabled={analyzeMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors disabled:opacity-50"
              aria-label={t("refresh")}
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${analyzeMutation.isPending ? "animate-spin" : ""}`}
              />
              {t("refresh")}
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
            aria-label={t("close")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* AI disclaimer — always visible per ADR-021 */}
      <div className="px-4 py-1.5 border-b border-border bg-muted/30">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="w-3.5 h-3.5 flex-shrink-0" />
          {t("betaReader.aiDisclaimer")}
        </p>
      </div>

      {/* Tabs */}
      {viewState === "results" && result && (
        <div className="flex border-b border-border bg-card">
          {TAB_CONFIG.map(({ key, icon: TabIcon }) => {
            const count =
              key === "strengths"
                ? result.strengths.length
                : key === "issues"
                  ? result.feedback.length
                  : key === "questions"
                    ? result.questions.length
                    : 0;

            return (
              <button
                key={key}
                type="button"
                onClick={() => setActiveTab(key)}
                className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm font-medium transition-colors border-b-2 ${
                  activeTab === key
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                <TabIcon className="w-4 h-4" />
                {t(`tabs.${key}`)}
                {key !== "overall" && (
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded ${activeTab === key ? "bg-primary/10" : "bg-muted"}`}
                  >
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          <BetaReaderPanelContent
            viewState={viewState}
            activeTab={activeTab}
            result={result}
            error={error}
            isPending={analyzeMutation.isPending}
            onRetry={() => void runAnalysis(false)}
            t={tFn}
          />
        </div>
      </div>

      {/* Footer — Deep Dive button */}
      {viewState === "results" && isCategoryTab && (
        <div className="p-4 border-t border-border bg-card">
          <button
            type="button"
            disabled={deepDiveMutation.isPending}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors disabled:opacity-50"
            onClick={() => {
              if (!result) return;
              const categories = (
                activeTab === "strengths"
                  ? result.strengths
                  : activeTab === "issues"
                    ? result.feedback
                    : result.questions
              ).map((item) => item.category);
              const mostCommon = categories.sort(
                (a, b) =>
                  categories.filter((c) => c === b).length -
                  categories.filter((c) => c === a).length,
              )[0];
              if (mostCommon) void handleDeepDive(mostCommon);
            }}
          >
            {deepDiveMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {deepDiveCategory
                  ? t("deepDiveLoading", { category: t(`categories.${deepDiveCategory}`) })
                  : t("deepDive")}
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                {t("deepDive")}
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
