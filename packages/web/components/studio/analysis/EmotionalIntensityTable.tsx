"use client";

/**
 * EmotionalIntensityTable — accessible data alternative (CR-AUFG-07-23).
 *
 * Renders the same per-chapter intensity information as the curve chart in
 * EmotionalIntensityCurve, but as a keyboard-accessible table so screen-reader
 * users get the full picture. Each chapter cell is a button that selects the
 * point (keeping table-row semantics while remaining keyboard-operable).
 *
 * Extracted from EmotionalIntensityCurve to satisfy RULE-04 file-size limits.
 */

import { useTranslations } from "next-intl";
import { useCallback } from "react";
import type { IntensityPoint } from "./intensity";

// --- Types -------------------------------------------------------------------

export interface EmotionalIntensityTableProps {
  /** Derived intensity points (one per chapter, positional). */
  points: IntensityPoint[];
  /** Called with the chapter index when a row is selected. When omitted the
   *  chapter buttons render disabled. */
  onPointClick?: (chapterIndex: number) => void;
}

// --- Component ---------------------------------------------------------------

export function EmotionalIntensityTable({ points, onPointClick }: EmotionalIntensityTableProps) {
  const t = useTranslations("analysis");

  const handlePointSelect = useCallback(
    (index: number) => {
      onPointClick?.(index);
    },
    [onPointClick],
  );

  return (
    <table className="w-full text-xs" aria-label={t("emotionalIntensity.tableSummary")}>
      <thead>
        <tr className="text-muted-foreground">
          <th scope="col" className="text-left font-medium py-1">
            {t("emotionalIntensity.tableHeaderChapter")}
          </th>
          <th scope="col" className="text-right font-medium py-1">
            {t("emotionalIntensity.tableHeaderIntensity")}
          </th>
          <th scope="col" className="text-right font-medium py-1">
            {t("emotionalIntensity.tableHeaderArousal")}
          </th>
          <th scope="col" className="text-left font-medium py-1">
            {t("emotionalIntensity.tableHeaderWarnings")}
          </th>
        </tr>
      </thead>
      <tbody>
        {points.map((p) => {
          const label =
            p.chapterTitle || t("emotionalIntensity.chapterLabel", { number: p.order + 1 });
          return (
            <tr key={p.chapterId ?? `intensity-${p.order}`} className="border-t border-border">
              <td className="py-1">
                <button
                  type="button"
                  onClick={() => handlePointSelect(p.order)}
                  className="text-left hover:underline focus:outline-none focus:underline disabled:opacity-50 disabled:no-underline"
                  aria-label={t("emotionalIntensity.pointAriaLabel", {
                    chapter: label,
                    intensity: p.intensity.toFixed(0),
                  })}
                  disabled={!onPointClick}
                >
                  {label}
                </button>
              </td>
              <td className="text-right tabular-nums py-1">{p.intensity.toFixed(0)}</td>
              <td className="text-right tabular-nums py-1">{p.arousal.toFixed(2)}</td>
              <td className="py-1 text-muted-foreground">
                {p.warnings.map((w) => (
                  <span key={w.kind}>{t(w.messageKey)}</span>
                ))}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
