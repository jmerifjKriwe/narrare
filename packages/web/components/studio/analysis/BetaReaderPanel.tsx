"use client";

/**
 * BetaReaderPanel — collapsible analysis results panel with 4 tabs.
 * Tabs: Strengths | Issues | Questions | Overall. Deep Dive on category tabs.
 * §16 compliance: useAIOperation-backed mutations for connection state.
 */

import { Info } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { AnalysisPanelWrapper } from "@/components/ui/analysis-panel-wrapper";
import { ConnectionLostBanner } from "@/components/ui/connection-lost-banner";
import type { BetaReaderResponse, FeedbackCategory } from "@/lib/api/analysis";
import { useBetaReaderAnalyze, useBetaReaderDeepDive } from "@/lib/hooks/useBetaReader";
import { useEditorStore } from "@/lib/stores/editorStore";
import { BetaReaderDeepDiveFooter } from "./BetaReaderDeepDiveFooter";
import { BetaReaderHeader } from "./BetaReaderHeader";
import { BetaReaderPanelContent, type BetaTab, type ViewState } from "./BetaReaderPanelContent";
import { BetaReaderTabBar } from "./BetaReaderTabBar";

interface BetaReaderPanelProps {
  readonly novelId: string;
  readonly chapterIds: string[];
  readonly onClose: () => void;
}

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
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err : new Error(String(err)));
        setViewState("error");
      } finally {
        setBetaReaderLoading(false);
      }
    },
    [chapterIds, analyzeMutation, setBetaReaderResult, setBetaReaderLoading],
  );

  // biome-ignore lint/correctness/useExhaustiveDependencies: mount-only
  useEffect(() => {
    if (viewState === "idle") void runAnalysis(false);
  }, []);

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

  const handleCancel = useCallback(() => {
    analyzeMutation.abort();
    setViewState("idle");
  }, [analyzeMutation]);
  const isCategoryTab =
    activeTab === "strengths" || activeTab === "issues" || activeTab === "questions";
  const tFn = (key: string, params?: Record<string, unknown>) =>
    t(key as Parameters<typeof t>[0], params as Parameters<typeof t>[1]) as string;

  return (
    <div className="flex flex-col h-full border-l border-border bg-background w-[400px] min-w-[400px]">
      <BetaReaderHeader
        viewState={viewState}
        isPending={analyzeMutation.isPending}
        onClose={onClose}
        onRefresh={() => void runAnalysis(true)}
      />
      <div className="px-4 py-1.5 border-b border-border bg-muted/30">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="w-3.5 h-3.5 flex-shrink-0" />
          {t("betaReader.aiDisclaimer")}
        </p>
      </div>
      <AnalysisPanelWrapper phase={viewState}>
        {analyzeMutation.isConnectionLost && (
          <div className="p-4 pb-0">
            <ConnectionLostBanner onRetry={() => analyzeMutation.retry()} />
          </div>
        )}
        {viewState === "results" && (
          <BetaReaderTabBar activeTab={activeTab} result={result} onTabChange={setActiveTab} />
        )}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto p-6 space-y-4">
            <BetaReaderPanelContent
              viewState={viewState}
              activeTab={activeTab}
              result={result}
              error={error}
              isPending={analyzeMutation.isPending}
              onRetry={() => void runAnalysis(false)}
              onCancel={viewState === "loading" ? handleCancel : undefined}
              t={tFn}
            />
          </div>
        </div>
        {viewState === "results" && isCategoryTab && (
          <BetaReaderDeepDiveFooter
            activeTab={activeTab}
            result={result}
            isPending={deepDiveMutation.isPending}
            deepDiveCategory={deepDiveCategory}
            onDeepDive={(category) => void handleDeepDive(category)}
          />
        )}
      </AnalysisPanelWrapper>
    </div>
  );
}
