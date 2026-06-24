"use client";

/**
 * SentimentResults — results display for sentiment analysis.
 *
 * Renders chapter selector, cross-chapter arc, VAD gauges, emotion chart
 * (with PNG export), narrative arc card, and per-sentence breakdown.
 */

import { toPng } from "html-to-image";
import { Download } from "lucide-react";
import { useCallback, useRef } from "react";

import type { SentimentOverview } from "@/lib/api/analysis";
import { EmotionalIntensityCurve } from "../EmotionalIntensityCurve";
import { SentimentArcGraph } from "../SentimentArcGraph";
import { SentimentChart } from "../SentimentChart";
import { SentenceRow } from "./SentimentSentenceRow";
import { VadGauge } from "./SentimentVadGauge";

interface SentimentResultsProps {
  results: SentimentOverview[];
  activeResult: SentimentOverview;
  activeChapterIdx: number;
  onChapterSelect: (idx: number) => void;
  t: (key: string, params?: Record<string, unknown>) => string;
}

export function SentimentResults({
  results,
  activeResult,
  activeChapterIdx,
  onChapterSelect,
  t,
}: SentimentResultsProps) {
  const chartRef = useRef<HTMLDivElement>(null);

  const handleExportChart = useCallback(async () => {
    if (!chartRef.current) return;
    try {
      const dataUrl = await toPng(chartRef.current, { backgroundColor: "#fff" });
      const link = document.createElement("a");
      link.download = "sentiment-chart.png";
      link.href = dataUrl;
      link.click();
    } catch (err) {
      // Export failure is non-critical — silently ignore
      console.error("Chart export failed:", err);
    }
  }, []);

  return (
    <>
      {/* Chapter selector (multi-chapter) */}
      {results.length > 1 && (
        <div className="flex gap-1 border-b border-border pb-3">
          {results.map((res, idx) => (
            <button
              key={`chapter-tab-${res.sentence_count}-${res.dominant_emotions.join(",")}`}
              type="button"
              onClick={() => onChapterSelect(idx)}
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

      {/* Cross-chapter arc trajectory (ANAL-002 #1) */}
      {results.length >= 2 && <SentimentArcGraph results={results} />}

      {/* Cross-chapter emotional intensity curve (CR-AUFG-07-23) */}
      {results.length >= 2 && (
        <EmotionalIntensityCurve results={results} onPointClick={onChapterSelect} />
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
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-medium">{t("sentiment.emotionChart")}</h4>
          <button
            type="button"
            onClick={() => void handleExportChart()}
            className="flex items-center gap-1 px-2 py-1 text-xs text-muted-foreground border border-border rounded-md hover:bg-muted transition-colors"
            aria-label={t("sentiment.exportChart")}
          >
            <Download className="w-3 h-3" />
            {t("sentiment.exportChart")}
          </button>
        </div>
        <div ref={chartRef} className="bg-background p-2 rounded-lg">
          <SentimentChart emotions={activeResult.overall_emotions} />
        </div>
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
            <SentenceRow key={`sent-${s.sentence_index}`} sentence={s} t={t} />
          ))}
        </div>
      </section>
    </>
  );
}
