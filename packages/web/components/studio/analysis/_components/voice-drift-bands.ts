/**
 * Voice-drift band metadata + classification-badge composition (ANAL-009).
 *
 * Pure presentational logic + design tokens for the Layout γ visualization
 * (ADR-073 Decision 4). Extracted into its own module so the heatmap / detail
 * card / legend sub-components share ONE source of band → colour / symbol /
 * label mapping (RULE-06 — one responsibility per file; RULE-04 — keeps each
 * component under its size limit).
 *
 * Band ↔ match score (identical thresholds to WRITE-010's `band_for_score`):
 *  - stable   ≥ 90  (green  ●)
 *  - minor    70–89 (yellow ▲)
 *  - moderate 50–69 (orange ◆)
 *  - major    < 50  (red    ◇)
 *
 * The score is a **match score** (100 = matches the stored profile perfectly) —
 * labelled "match to profile" to avoid the inverted meaning of "drift %"
 * (ADR-073 Decision 4 terminology).
 *
 * The row classification badge is a **display label derived from the band +
 * the agent's `drift_type`** (ADR-073 D4). The composition rule (guided by the
 * approved mockup):
 *  - stable band  → "Stable" (the voice is not drifting)
 *  - minor band   → "Mild variation" (band-derived; the drift_type is not surfaced)
 *  - moderate/major band → the agent's `drift_type` label (Evolution / Context /
 *    Inconsistent) — the qualitative call is the valuable signal at this depth
 *  - null band     → no badge (unscorable)
 *
 * @module voice-drift-bands
 */

import type { VoiceDriftBand, VoiceDriftType } from "@/lib/api/voice-drift-stream";

/** The drift classification badge label key (i18n: `voiceDrift.classification.*`). */
export type VoiceDriftClassification =
  | "stable"
  | "mildVariation"
  | "evolution"
  | "context"
  | "inconsistency";

/** Metadata for one drift band (label / symbol / Tailwind colour tokens). */
export interface VoiceDriftBandMeta {
  /** i18n key suffix: `voiceDrift.band.{label}`. */
  readonly label: VoiceDriftBand;
  /** Cell / dot symbol (matches the approved mockup). */
  readonly symbol: string;
  /** Tailwind text colour token for the band (cell symbol + dot). */
  readonly text: string;
  /** Tailwind background token for a heatmap cell. */
  readonly cellBg: string;
  /** Tailwind border token for a heatmap cell. */
  readonly cellBorder: string;
  /** Tailwind classes for a badge pill of this band's colour. */
  readonly badge: string;
}

/** Ordered band metadata (stable → major). Index 0 is the best match. */
export const DRIFT_BANDS: Record<VoiceDriftBand, VoiceDriftBandMeta> = {
  stable: {
    label: "stable",
    symbol: "\u25CF", // ●
    text: "text-emerald-600 dark:text-emerald-400",
    cellBg: "bg-emerald-500/10",
    cellBorder: "border-emerald-500/30",
    badge:
      "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700",
  },
  minor: {
    label: "minor",
    symbol: "\u25B2", // ▲
    text: "text-yellow-600 dark:text-yellow-400",
    cellBg: "bg-yellow-500/10",
    cellBorder: "border-yellow-500/30",
    badge:
      "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300 border-yellow-300 dark:border-yellow-700",
  },
  moderate: {
    label: "moderate",
    symbol: "\u25C6", // ◆
    text: "text-orange-600 dark:text-orange-400",
    cellBg: "bg-orange-500/10",
    cellBorder: "border-orange-500/30",
    badge:
      "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300 border-orange-300 dark:border-orange-700",
  },
  major: {
    label: "major",
    symbol: "\u25C7", // ◇
    text: "text-red-600 dark:text-red-400",
    cellBg: "bg-red-500/10",
    cellBorder: "border-red-500/30",
    badge:
      "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 border-red-300 dark:border-red-700",
  },
};

/** All bands in display order (stable → major). */
export const DRIFT_BAND_ORDER: readonly VoiceDriftBand[] = ["stable", "minor", "moderate", "major"];

/**
 * Compose the row classification badge label from the overall band + the
 * agent's drift_type (ADR-073 Decision 4 — frontend concern, guided by the
 * approved mockup). Returns `null` when the character is unscorable (no band).
 */
export function composeClassification(
  overallBand: VoiceDriftBand | null,
  driftType: VoiceDriftType,
): VoiceDriftClassification | null {
  if (overallBand === null) return null;
  if (overallBand === "stable") return "stable";
  if (overallBand === "minor") return "mildVariation";
  // moderate / major → surface the agent's qualitative drift_type label.
  return driftType;
}

/** Format a match score [0, 100] as a rounded integer percentage string. */
export function formatMatchPercent(score: number | null): string | null {
  if (score == null) return null;
  return `${Math.round(score)}%`;
}
