"use client";

/**
 * ReadabilityResultsView — renders the analysis results content.
 *
 * Contains chapter selector tabs, score bars, text statistics,
 * genre comparison, sentence analysis rows, and overall assessment.
 * Requires "use client" for chapter tab selection (setActiveChapterIdx).
 */

import type { ReadabilityResult } from "@/lib/api/analysis";
import { ReadabilityGenreComparison } from "./ReadabilityGenreComparison";
import { ReadabilityMetricCard } from "./ReadabilityMetricCard";
import { ReadabilityScoreBar } from "./ReadabilityScoreBar";
import { ReadabilitySentenceRow } from "./ReadabilitySentenceRow";

interface ReadabilityResultsViewProps {
  results: ReadabilityResult[];
  activeChapterIdx: number;
  onChapterChange: (idx: number) => void;
  t: (key: string, params?: Record<string, unknown>) => string;
}

export function ReadabilityResultsView({
  results,
  activeChapterIdx,
  onChapterChange,
  t,
}: ReadabilityResultsViewProps) {
  const activeResult = results[activeChapterIdx];

  if (!activeResult) return null;

  return (
    <>
      {/* Chapter selector (multi-chapter) */}
      {results.length > 1 && (
        <div className="flex gap-1 border-b border-border pb-3">
          {results.map((res, idx) => (
            <button
              key={`chapter-tab-${res.metrics.word_count}-${res.metrics.sentence_count}`}
              type="button"
              onClick={() => onChapterChange(idx)}
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
          <ReadabilityScoreBar
            label={t("readability.fleschReadingEase")}
            score={activeResult.metrics.flesch_reading_ease}
          />
          <ReadabilityScoreBar
            label={t("readability.fleschKincaidGrade")}
            score={18 - activeResult.metrics.flesch_kincaid_grade}
            maxScore={18}
          />
          <ReadabilityScoreBar
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
          <ReadabilityMetricCard
            label={t("readability.wordCount")}
            value={activeResult.metrics.word_count.toLocaleString()}
          />
          <ReadabilityMetricCard
            label={t("readability.sentenceCount")}
            value={activeResult.metrics.sentence_count.toLocaleString()}
          />
          <ReadabilityMetricCard
            label={t("readability.avgSentenceLength")}
            value={activeResult.metrics.avg_sentence_length.toFixed(1)}
            unit={t("readability.wordsUnit")}
          />
          <ReadabilityMetricCard
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
              <ReadabilityGenreComparison
                key={`genre-${genreKey}`}
                label={getGenreLabel(t, genreKey)}
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
              <ReadabilitySentenceRow key={`sent-${s.sentence_index}`} sentence={s} t={t} />
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
  );
}

// --- Helpers ---

function getGenreLabel(
  t: (key: string, params?: Record<string, unknown>) => string,
  genreKey: string,
): string {
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
