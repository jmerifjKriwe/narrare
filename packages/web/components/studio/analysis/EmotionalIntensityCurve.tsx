"use client";

/**
 * EmotionalIntensityCurve — CR-AUFG-07-23
 *
 * Frontend-only visualization of existing ANAL-002 sentiment data. Maps each
 * chapter's `average_vad.arousal` to an estimated intensity point and renders
 * an area curve across chapters.
 *
 * Grounding guarantees (CR-AUFG-07-23):
 * - No new backend, LLM, or prompt: derives everything from SentimentOverview.
 * - Never claims reader emotion: uses "estimated intensity" language and
 *   surfaces only data-quality warnings (e.g. too few sentences).
 *
 * Accessibility:
 * - Chart wrapper has role="img" + aria-label.
 * - A data table provides the same information as a screen-reader alternative;
 *   each chapter cell is a keyboard-accessible button that selects the point.
 */

import { toPng } from "html-to-image";
import { Download } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useMemo, useRef } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SentimentOverview } from "@/lib/api/analysis";
import { EmotionalIntensityTable } from "./EmotionalIntensityTable";
import { deriveIntensityPoints, type IntensityChapter } from "./intensity";

// --- Types -------------------------------------------------------------------

export interface EmotionalIntensityCurveProps {
  /** Per-chapter sentiment results (positional: results[i] ↔ chapter i). */
  results: SentimentOverview[];
  /** Optional chapter metadata (id + title) at the same indices as results. */
  chapters?: IntensityChapter[];
  /** Called with the chapter index when a point/row is selected. */
  onPointClick?: (chapterIndex: number) => void;
}

// Minimum number of chapters required to draw a meaningful curve.
const MIN_CHAPTERS_FOR_CURVE = 2;

// --- Component ---------------------------------------------------------------

export function EmotionalIntensityCurve({
  results,
  chapters,
  onPointClick,
}: EmotionalIntensityCurveProps) {
  const t = useTranslations("analysis");
  const chartRef = useRef<HTMLDivElement>(null);

  const points = useMemo(() => deriveIntensityPoints(results, chapters), [results, chapters]);

  const chartData = useMemo(
    () =>
      points.map((p) => ({
        label: p.chapterTitle || t("emotionalIntensity.chapterLabel", { number: p.order + 1 }),
        intensity: p.intensity,
      })),
    [points, t],
  );

  const handleExport = useCallback(async () => {
    if (!chartRef.current) return;
    try {
      const dataUrl = await toPng(chartRef.current, { backgroundColor: "#fff" });
      const link = document.createElement("a");
      link.download = "emotional-intensity-curve.png";
      link.href = dataUrl;
      link.click();
    } catch (err) {
      // Export failure is non-critical — silently ignore
      console.error("Intensity curve export failed:", err);
    }
  }, []);

  // --- Empty state: nothing analyzed yet -------------------------------------

  if (results.length === 0) {
    return (
      <section aria-label={t("emotionalIntensity.title")}>
        <p className="text-sm text-muted-foreground">{t("emotionalIntensity.empty")}</p>
      </section>
    );
  }

  // --- Insufficient data: a curve needs >= 2 chapters ------------------------

  if (results.length < MIN_CHAPTERS_FOR_CURVE) {
    return (
      <section aria-label={t("emotionalIntensity.title")}>
        <p className="text-sm text-muted-foreground">{t("emotionalIntensity.insufficientData")}</p>
      </section>
    );
  }

  // --- Curve + accessible table ---------------------------------------------

  return (
    <section aria-label={t("emotionalIntensity.title")} className="space-y-3">
      <div>
        <h4 className="text-sm font-medium">{t("emotionalIntensity.title")}</h4>
        <p className="text-xs text-muted-foreground">{t("emotionalIntensity.disclaimer")}</p>
        <p className="text-xs text-muted-foreground mt-1">
          {t("emotionalIntensity.scoreExplanation")}
        </p>
      </div>

      {/* Chart */}
      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={() => void handleExport()}
          className="flex items-center gap-1 px-2 py-1 text-xs text-muted-foreground border border-border rounded-md hover:bg-muted transition-colors"
          aria-label={t("emotionalIntensity.exportChart")}
        >
          <Download className="w-3 h-3" />
          {t("emotionalIntensity.exportChart")}
        </button>
      </div>
      <div ref={chartRef} className="bg-background p-2 rounded-lg">
        <div className="w-full" role="img" aria-label={t("emotionalIntensity.title")}>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={chartData} margin={{ left: 0, right: 16, top: 4, bottom: 4 }}>
              <defs>
                <linearGradient id="intensityGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.5} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                tickCount={6}
              />
              <Tooltip
                formatter={(value) => [
                  Number(value).toFixed(0),
                  t("emotionalIntensity.estimatedLabel"),
                ]}
              />
              <Area
                type="monotone"
                dataKey="intensity"
                stroke="#f59e0b"
                strokeWidth={2}
                fill="url(#intensityGradient)"
                dot
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Accessible data alternative */}
      <EmotionalIntensityTable points={points} onPointClick={onPointClick} />
    </section>
  );
}
