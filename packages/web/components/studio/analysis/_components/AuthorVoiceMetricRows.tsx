"use client";

/**
 * AuthorVoiceMetricRows — row builders for the advanced-metrics groups
 * (ANAL-007 / ADR-074).
 *
 * Extracted from {@link AuthorVoiceAdvancedMetrics} per RULE-04: the metric
 * row-building helpers (`voiceRows` / `authorRows`) plus their shared
 * {@link MetricRow} + numeric formatters form a cohesive concern and pushed
 * the parent past the 200-line component limit once biome-formatted. Pure
 * presentational helpers — no state, no hooks.
 *
 * @module AuthorVoiceMetricRows
 */

import type { ReactElement } from "react";
import type { AuthorMetrics, VoiceMetrics } from "@/lib/api/author-voice-stream";

type TranslationFunc = (key: string, values?: Record<string, string | number | Date>) => string;

/**
 * Build the deterministic voice-GENERIC metric rows (avg sentence length, TTR,
 * syllables, contraction rate, punctuation profile). Only non-null fields
 * produce a row.
 */
export function voiceRows(metrics: VoiceMetrics, t: TranslationFunc): ReactElement[] {
  const out: ReactElement[] = [];
  if (metrics.avg_sentence_length != null)
    out.push(
      <MetricRow
        key="asl"
        label={t("authorVoice.avgSentenceLength")}
        value={fmt(metrics.avg_sentence_length)}
      />,
    );
  if (metrics.sentence_length_std != null)
    out.push(
      <MetricRow
        key="sls"
        label={t("authorVoice.sentenceLengthStd")}
        value={fmt(metrics.sentence_length_std)}
      />,
    );
  if (metrics.type_token_ratio != null)
    out.push(
      <MetricRow
        key="ttr"
        label={t("authorVoice.typeTokenRatio")}
        value={fmt(metrics.type_token_ratio)}
      />,
    );
  if (metrics.avg_syllables_per_word != null)
    out.push(
      <MetricRow
        key="aspw"
        label={t("authorVoice.avgSyllablesPerWord")}
        value={fmt(metrics.avg_syllables_per_word)}
      />,
    );
  if (metrics.contraction_rate != null)
    out.push(
      <MetricRow
        key="cr"
        label={t("authorVoice.contractionRate")}
        value={fmtPct(metrics.contraction_rate)}
      />,
    );
  if (metrics.punctuation_profile != null) {
    const joined = Object.entries(metrics.punctuation_profile)
      .map(([k, v]) => `${k}: ${fmt(v)}`)
      .join(", ");
    out.push(<MetricRow key="pp" label={t("authorVoice.punctuationProfile")} value={joined} />);
  }
  return out;
}

/** Build the author-specific prose-level metric rows (dialogue / description / action / metaphor). */
export function authorRows(metrics: AuthorMetrics, t: TranslationFunc): ReactElement[] {
  const out: ReactElement[] = [];
  if (metrics.dialogue_ratio != null)
    out.push(
      <MetricRow
        key="dr"
        label={t("authorVoice.dialogueRatio")}
        value={fmtPct(metrics.dialogue_ratio)}
      />,
    );
  if (metrics.description_density != null)
    out.push(
      <MetricRow
        key="dd"
        label={t("authorVoice.descriptionDensity")}
        value={fmtPct(metrics.description_density)}
      />,
    );
  if (metrics.action_introspection_ratio != null)
    out.push(
      <MetricRow
        key="air"
        label={t("authorVoice.actionIntrospectionRatio")}
        value={fmtPct(metrics.action_introspection_ratio)}
      />,
    );
  if (metrics.metaphor_density != null)
    out.push(
      <MetricRow
        key="md"
        label={t("authorVoice.metaphorDensity")}
        value={fmtPct(metrics.metaphor_density)}
      />,
    );
  return out;
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-xs text-muted-foreground flex-shrink-0">{label}</dt>
      <dd className="text-sm font-medium tabular-nums text-right">{value}</dd>
    </div>
  );
}

/** Numeric metric → fixed-point string (2 decimals). */
function fmt(value: number): string {
  return value.toFixed(2);
}

/** Ratio (0.0–1.0) → percentage string. */
function fmtPct(value: number): string {
  return `${Math.round(value * 100)}%`;
}
