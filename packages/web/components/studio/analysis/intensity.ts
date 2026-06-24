/**
 * Intensity derivation — CR-AUFG-07-23 Emotional Intensity Curve.
 *
 * Pure functions that map existing ANAL-002 SentimentOverview data onto
 * chapter-level intensity points. No I/O, no React — fully unit-testable.
 *
 * Design notes:
 * - `arousal` (-1 = calm, +1 = excited) is the intensity signal.
 * - It is normalized to a 0..100 display scale for the curve.
 * - Warnings are *data-quality* signals derived deterministically
 *   (e.g. too few sentences for a reliable estimate). They never make
 *   reader-emotion claims — consistent with the "estimated intensity"
 *   language required by CR-AUFG-07-23.
 */

import type { SentimentOverview } from "@/lib/api/analysis";

// --- Types -------------------------------------------------------------------

/** Minimal chapter metadata used to label a curve point. */
export interface IntensityChapter {
  id: string;
  title: string;
}

/** Kinds of data-quality warnings a point can carry. */
export type IntensityWarningKind = "insufficient_sentences";

export interface IntensityWarning {
  kind: IntensityWarningKind;
  /** i18n key under the `analysis` namespace, e.g. emotionalIntensity.warnings.* */
  messageKey: string;
}

export interface IntensityPoint {
  /** Zero-based position in chapter order. */
  order: number;
  /** Chapter id when known, else null (results are positional). */
  chapterId: string | null;
  /** Raw chapter title when available; empty string when unknown. */
  chapterTitle: string;
  /** Raw arousal (-1..+1) from ANAL-002. */
  arousal: number;
  /** Normalized intensity on a 0..100 display scale. */
  intensity: number;
  /** Narrative-arc confidence when available, else null. */
  confidence: number | null;
  /** Data-quality warnings for this point. */
  warnings: IntensityWarning[];
}

// --- Constants ---------------------------------------------------------------

/**
 * Minimum number of analyzed sentences for the arousal average to be
 * considered a reliable intensity estimate. Below this the point carries
 * an "insufficient sentences" warning.
 */
export const MIN_SENTENCES_FOR_RELIABLE = 3;

// --- Functions ---------------------------------------------------------------

/**
 * Map a raw arousal value (-1..+1) onto the 0..100 intensity display scale.
 * Values outside [-1, +1] are clamped to the scale edges.
 */
export function arousalToIntensity(arousal: number): number {
  const clamped = Math.max(-1, Math.min(1, arousal));
  // Round to 1 decimal place: this is a 0..100 display scale, so rounding
  // avoids floating-point noise (e.g. -0.8 → 9.9999… instead of 10) without
  // losing meaningful granularity.
  return Math.round(((clamped + 1) / 2) * 100 * 10) / 10;
}

/**
 * Derive ordered intensity points from ANAL-002 sentiment overviews.
 *
 * `results` is positional: `results[i]` corresponds to chapter `i`.
 * The optional `chapters` array provides ids/titles at the same indices;
 * when omitted the points fall back to a null id and empty title, and the
 * presentation layer supplies a positional label.
 */
export function deriveIntensityPoints(
  results: SentimentOverview[],
  chapters?: IntensityChapter[],
): IntensityPoint[] {
  return results.map((result, idx) => {
    const chapter = chapters?.[idx];

    const warnings: IntensityWarning[] = [];
    if (result.sentence_count < MIN_SENTENCES_FOR_RELIABLE) {
      warnings.push({
        kind: "insufficient_sentences",
        messageKey: "emotionalIntensity.warnings.insufficientSentences",
      });
    }

    const confidence = result.narrative_arc?.confidence ?? null;

    return {
      order: idx,
      chapterId: chapter?.id ?? null,
      chapterTitle: chapter?.title ?? "",
      arousal: result.average_vad.arousal,
      intensity: arousalToIntensity(result.average_vad.arousal),
      confidence,
      warnings,
    };
  });
}
