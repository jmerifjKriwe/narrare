"use client";

/**
 * ReadabilityPanel — collapsible side panel for Readability Analysis (ANAL-003).
 *
 * Shows readability metrics, genre comparison, problematic sentences with
 * suggestions, and overall AI assessment.
 * Follows SentimentPanel layout (400px wide, border-left).
 * Multi-chapter support via chapter selector tabs.
 */

import {
  ArrowLeft,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Info,
  Loader2,
  RefreshCw,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { ReadabilityResult } from "@/lib/api/analysis";
import { useReadabilityAnalysis } from "@/lib/hooks/useReadability";

// --- Types ---

interface ReadabilityPanelProps {
  novelId: string;
  chapterIds: string[];
  onClose: () => void;
}

// --- Helper: score color class ---

function getScoreColorClass(score: number): string {
  if (score >= 60) return "text-green-600 dark:text-green-400";
  if (score >= 30) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-600 dark:text-red-400";
}

function getScoreBarClass(score: number): string {
  if (score >= 60) return "bg-green-500";
  if (score >= 30) return "bg-yellow-500";
  return "bg-red-500";
}

// --- Metric card ---

function MetricCard({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="rounded-lg border border-border p-3 bg-background">
      <div className="text-xs text-muted-foreground mb-1">{label}</div>
      <div className="text-sm font-medium">
        {value}
        {unit && <span className="text-xs text-muted-foreground ml-1">{unit}</span>}
      </div>
    </div>
  );
}

// --- Score bar ---

function ScoreBar({
  label,
  score,
  maxScore = 100,
}: {
  label: string;
  score: number;
  maxScore?: number;
}) {
  const percentage = Math.min(100, Math.max(0, (score / maxScore) * 100));

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className={`text-xs font-medium ${getScoreColorClass(score)}`}>
          {score.toFixed(1)}
        </span>
      </div>
      <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${getScoreBarClass(score)}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

// --- Genre comparison bar ---

function GenreComparison({
  label,
  benchmark,
  actual,
}: {
  label: string;
  benchmark: number;
  actual: number;
}) {
  const diff = actual - benchmark;
  const isBetter = diff >= 0;

  return (
    <div className="flex items-center justify-between rounded-lg border border-border p-3 bg-background">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">{benchmark.toFixed(1)}</span>
        <span
          className={`text-xs font-medium ${isBetter ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
        >
          {isBetter ? "+" : ""}
          {diff.toFixed(1)}
        </span>
      </div>
    </div>
  );
}

// --- Sentence analysis row ---

function SentenceRow({
  sentence,
  t,
}: {
  sentence: ReadabilityResult["sentence_analyses"][number];
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const scorePercent = Math.round(sentence.readability_score * 100);
  const scoreColor =
    sentence.readability_score >= 0.7
      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
      : sentence.readability_score >= 0.4
        ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
        : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400";

  return (
    <div className="rounded border border-border p-3">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-left"
        aria-expanded={expanded}
      >
        <span className="text-xs text-muted-foreground flex items-center gap-1.5 min-w-0 flex-1">
          <span className={`text-xs font-medium px-1.5 py-0.5 rounded flex-shrink-0 ${scoreColor}`}>
            {scorePercent}%
          </span>
          <span className="truncate">{sentence.sentence}</span>
        </span>
        <span className="text-xs text-muted-foreground flex-shrink-0 ml-2">
          {expanded ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
        </span>
      </button>
      {expanded && (
        <div className="mt-2 space-y-2 text-xs">
          {/* Issues list */}
          {sentence.issues.length > 0 && (
            <div className="space-y-1">
              {sentence.issues.map((issue) => (
                <div
                  key={`issue-${sentence.sentence_index}-${issue}`}
                  className="flex items-start gap-1.5 text-muted-foreground"
                >
                  <span className="mt-1 w-1 h-1 rounded-full bg-yellow-500 flex-shrink-0" />
                  <span>{issue}</span>
                </div>
              ))}
            </div>
          )}
          {/* Suggestions toggle */}
          {sentence.suggestions.length > 0 && (
            <div>
              <button
                type="button"
                onClick={() => setShowSuggestions(!showSuggestions)}
                className="text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300 font-medium flex items-center gap-1"
              >
                {showSuggestions ? (
                  <ChevronUp className="w-3 h-3" />
                ) : (
                  <ChevronDown className="w-3 h-3" />
                )}
                {t("readability.suggestions")} ({sentence.suggestions.length})
              </button>
              {showSuggestions && (
                <div className="mt-1.5 space-y-1.5">
                  {sentence.suggestions.map((suggestion) => (
                    <div
                      key={`suggestion-${sentence.sentence_index}-${suggestion.slice(0, 30)}`}
                      className="rounded bg-muted/50 p-2 text-muted-foreground italic"
                    >
                      {suggestion}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// --- Component ---

export function ReadabilityPanel({ novelId, chapterIds, onClose }: ReadabilityPanelProps) {
  const t = useTranslations("analysis");

  const [viewState, setViewState] = useState<"idle" | "loading" | "results" | "error">("idle");
  const [results, setResults] = useState<ReadabilityResult[] | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [activeChapterIdx, setActiveChapterIdx] = useState(0);

  const analyzeMutation = useReadabilityAnalysis(novelId);

  // --- Run analysis ---

  const runAnalysis = useCallback(
    async (_refresh = false) => {
      if (chapterIds.length === 0) return;
      setViewState("loading");
      setError(null);

      try {
        const res = await analyzeMutation.mutateAsync({
          chapter_ids: chapterIds,
        });
        setResults(res);
        setViewState("results");
        setActiveChapterIdx(0);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setViewState("error");
      }
    },
    [chapterIds, analyzeMutation],
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

  // --- Genre label mapping ---

  function getGenreLabel(genreKey: string): string {
    switch (genreKey) {
      case "middle_grade":
        return t("readability.middleGrade");
      case "young_adult":
        return t("readability.youngAdult");
      case "commercial_fiction":
        return t("readability.commercial");
      case "literary_fiction":
        return t("readability.literary");
      default:
        return genreKey;
    }
  }

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
            <BookOpen className="w-5 h-5 text-emerald-500 flex-shrink-0" />
            <h3 className="font-medium truncate">{t("readability.title")}</h3>
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

      {/* Info banner */}
      <div className="px-4 py-1.5 border-b border-border bg-muted/30">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="w-3.5 h-3.5 flex-shrink-0" />
          {t("readability.disclaimer")}
        </p>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6 space-y-4">
          {/* Loading state */}
          {viewState === "loading" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="relative mb-6">
                <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
                  <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
                </div>
              </div>
              <p className="text-lg font-medium mb-2">{t("readability.analyzing")}</p>
              <p className="text-sm text-muted-foreground">{t("readability.analyzingSubtext")}</p>
            </div>
          )}

          {/* Error state */}
          {viewState === "error" && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
                <Info className="w-6 h-6 text-red-500" />
              </div>
              <p className="text-lg font-medium mb-1">{t("readability.error")}</p>
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
                      key={`chapter-tab-${res.metrics.word_count}-${res.metrics.sentence_count}`}
                      type="button"
                      onClick={() => setActiveChapterIdx(idx)}
                      className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
                        activeChapterIdx === idx
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {t("readability.chapter", { number: idx + 1 })}
                    </button>
                  ))}
                </div>
              )}

              {/* Core readability scores */}
              <section>
                <h4 className="text-sm font-medium mb-3">{t("readability.scores")}</h4>
                <div className="space-y-3">
                  <ScoreBar
                    label={t("readability.fleschReadingEase")}
                    score={activeResult.metrics.flesch_reading_ease}
                  />
                  <ScoreBar
                    label={t("readability.fleschKincaidGrade")}
                    score={18 - activeResult.metrics.flesch_kincaid_grade}
                    maxScore={18}
                  />
                  <ScoreBar
                    label={t("readability.gunningFog")}
                    score={20 - activeResult.metrics.gunning_fog}
                    maxScore={20}
                  />
                </div>
              </section>

              {/* Text statistics */}
              <section>
                <h4 className="text-sm font-medium mb-3">{t("readability.statistics")}</h4>
                <div className="grid grid-cols-2 gap-2">
                  <MetricCard
                    label={t("readability.wordCount")}
                    value={activeResult.metrics.word_count.toLocaleString()}
                  />
                  <MetricCard
                    label={t("readability.sentenceCount")}
                    value={activeResult.metrics.sentence_count.toLocaleString()}
                  />
                  <MetricCard
                    label={t("readability.avgSentenceLength")}
                    value={activeResult.metrics.avg_sentence_length.toFixed(1)}
                    unit={t("readability.wordsUnit")}
                  />
                  <MetricCard
                    label={t("readability.complexWordRatio")}
                    value={`${(activeResult.metrics.complex_word_ratio * 100).toFixed(1)}%`}
                  />
                </div>
              </section>

              {/* Genre comparison */}
              {Object.keys(activeResult.genre_benchmarks).length > 0 && (
                <section>
                  <h4 className="text-sm font-medium mb-3">{t("readability.genreComparison")}</h4>
                  <div className="space-y-2">
                    {Object.entries(activeResult.genre_benchmarks).map(([genreKey, benchmark]) => (
                      <GenreComparison
                        key={`genre-${genreKey}`}
                        label={getGenreLabel(genreKey)}
                        benchmark={benchmark.flesch_reading_ease}
                        actual={activeResult.metrics.flesch_reading_ease}
                      />
                    ))}
                  </div>
                </section>
              )}

              {/* Problematic sentences */}
              <section>
                <h4 className="text-sm font-medium mb-2">
                  {activeResult.sentence_analyses.length > 0
                    ? t("readability.problematicSentences", {
                        count: activeResult.sentence_analyses.length,
                      })
                    : t("readability.noIssues")}
                </h4>
                {activeResult.sentence_analyses.length > 0 && (
                  <div className="space-y-2">
                    {activeResult.sentence_analyses.map((s) => (
                      <SentenceRow key={`sent-${s.sentence_index}`} sentence={s} t={tFn} />
                    ))}
                  </div>
                )}
              </section>

              {/* Overall assessment */}
              {activeResult.overall_assessment && (
                <section>
                  <h4 className="text-sm font-medium mb-2">{t("readability.overallAssessment")}</h4>
                  <div className="rounded-lg border border-border p-3 text-sm text-muted-foreground">
                    {activeResult.overall_assessment}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
