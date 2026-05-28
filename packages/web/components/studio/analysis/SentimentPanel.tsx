"use client";

/**
 * SentimentPanel — collapsible side panel for Sentiment Analysis (ANAL-002).
 *
 * Shows VAD gauges, emotion chart, narrative arc, and per-sentence breakdown.
 * Follows BetaReaderPanel layout (400px wide, border-left).
 * Multi-chapter support via chapter selector tabs.
 */

import { ArrowLeft, Info, Loader2, RefreshCw, TrendingUp, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { SentimentOverview } from "@/lib/api/analysis";
import { useSentimentAnalyze } from "@/lib/hooks/useSentiment";
import { useEditorStore } from "@/lib/stores/editorStore";
import { SentimentChart } from "./SentimentChart";

// --- Types ---

interface SentimentPanelProps {
  novelId: string;
  chapterIds: string[];
  onClose: () => void;
}

// --- VAD gauge bar ---

function VadGauge({ label, value, color }: { label: string; value: number; color: string }) {
  // Map -1..+1 to 0..100% for display
  const percentage = ((value + 1) / 2) * 100;

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="text-xs font-medium">{value.toFixed(2)}</span>
      </div>
      <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

// --- Sentence row ---

function SentenceRow({
  sentence,
  t,
}: {
  sentence: SentimentOverview["sentences"][number];
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const [expanded, setExpanded] = useState(false);
  const emotionLabel = sentence.dominant_emotion ?? t("sentiment.noDominantEmotion");

  return (
    <div className="rounded border border-border p-3">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-left"
        aria-expanded={expanded}
      >
        <span className="text-xs text-muted-foreground flex items-center gap-1.5 min-w-0 flex-1">
          <span className="text-xs font-medium bg-muted px-1.5 py-0.5 rounded flex-shrink-0">
            {emotionLabel}
          </span>
          <span className="truncate">{sentence.sentence}</span>
        </span>
        <span className="text-xs text-muted-foreground flex-shrink-0 ml-2">
          {expanded ? "▲" : "▼"}
        </span>
      </button>
      {expanded && (
        <div className="mt-2 space-y-1 text-xs text-muted-foreground">
          <div className="flex gap-4">
            <span>
              {t("sentiment.vad.valenceShort")} {sentence.vad.valence.toFixed(2)}{" "}
              {t("sentiment.vad.arousalShort")} {sentence.vad.arousal.toFixed(2)}{" "}
              {t("sentiment.vad.dominanceShort")} {sentence.vad.dominance.toFixed(2)}
            </span>
            {sentence.is_dialogue && <span className="italic">{t("sentiment.dialogue")}</span>}
          </div>
          <span>{t("sentiment.wordCount", { count: sentence.word_count })}</span>
        </div>
      )}
    </div>
  );
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
            <TrendingUp className="w-5 h-5 text-blue-500 flex-shrink-0" />
            <h3 className="font-medium truncate">{t("sentiment.title")}</h3>
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

      {/* Deterministic disclaimer */}
      <div className="px-4 py-1.5 border-b border-border bg-muted/30">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="w-3.5 h-3.5 flex-shrink-0" />
          {t("sentiment.disclaimer")}
        </p>
      </div>

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
            <>
              {/* Chapter selector (multi-chapter) */}
              {results.length > 1 && (
                <div className="flex gap-1 border-b border-border pb-3">
                  {results.map((res, idx) => (
                    <button
                      key={`chapter-tab-${res.sentence_count}-${res.dominant_emotions.join(",")}`}
                      type="button"
                      onClick={() => setActiveChapterIdx(idx)}
                      className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
                        activeChapterIdx === idx
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {t("sentiment.chapter", { number: idx + 1 })}
                    </button>
                  ))}
                </div>
              )}

              {/* Average VAD */}
              <section>
                <h4 className="text-sm font-medium mb-3">{t("sentiment.vad.title")}</h4>
                <div className="space-y-3">
                  <VadGauge
                    label={t("sentiment.vad.valence")}
                    value={activeResult.average_vad.valence}
                    color="bg-blue-500"
                  />
                  <VadGauge
                    label={t("sentiment.vad.arousal")}
                    value={activeResult.average_vad.arousal}
                    color="bg-amber-500"
                  />
                  <VadGauge
                    label={t("sentiment.vad.dominance")}
                    value={activeResult.average_vad.dominance}
                    color="bg-green-500"
                  />
                </div>
              </section>

              {/* Emotion chart */}
              <section>
                <h4 className="text-sm font-medium mb-3">{t("sentiment.emotionChart")}</h4>
                <SentimentChart emotions={activeResult.overall_emotions} />
              </section>

              {/* Narrative arc */}
              {activeResult.narrative_arc && (
                <section>
                  <h4 className="text-sm font-medium mb-2">{t("sentiment.arc.title")}</h4>
                  <div className="rounded-lg border border-border p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium bg-muted px-2 py-0.5 rounded">
                        {activeResult.narrative_arc.arc_type}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {t("sentiment.arc.confidence", {
                          value: (activeResult.narrative_arc.confidence * 100).toFixed(0),
                        })}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {activeResult.narrative_arc.explanation}
                    </p>
                  </div>
                </section>
              )}

              {/* Sentence breakdown */}
              <section>
                <h4 className="text-sm font-medium mb-2">
                  {t("sentiment.sentences", { count: activeResult.sentences.length })}
                </h4>
                <div className="space-y-2">
                  {activeResult.sentences.map((s) => (
                    <SentenceRow key={`sent-${s.sentence_index}`} sentence={s} t={tFn} />
                  ))}
                </div>
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
