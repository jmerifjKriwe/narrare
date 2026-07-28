"use client";

/**
 * AuthorVoiceAdvancedMetrics — collapsible ADVANCED-METRICS section
 * (ANAL-007 / ADR-074).
 *
 * Displays the METRIC groups (`voice_analysis.voice_metrics` +
 * `author_metrics`) — these are diagnostic information for the writer but
 * NEVER reach generation (the descriptive/metric boundary, ADR-055/057/074,
 * is enforced at the Core `render_author_voice_for_generation` consumer; the
 * UI displays both groups freely).
 *
 * Collapsed by default so the writer is not overwhelmed. A clear
 * "diagnostic only" caveat labels the section. Extracted per RULE-04.
 */

import { ChevronDown, ChevronRight, Info } from "lucide-react";
import { useState } from "react";
import type {
  AuthorMetrics,
  AuthorVoiceProfile,
  VoiceMetrics,
} from "@/lib/api/author-voice-stream";
import { authorRows, voiceRows } from "./AuthorVoiceMetricRows";

interface AuthorVoiceAdvancedMetricsProps {
  profile: AuthorVoiceProfile;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function AuthorVoiceAdvancedMetrics({ profile, t }: AuthorVoiceAdvancedMetricsProps) {
  const [open, setOpen] = useState(false);
  const voiceMetrics = profile.voice_analysis?.voice_metrics ?? null;
  const authorMetrics = profile.author_metrics ?? null;

  // Hide the section entirely when no metrics are present.
  if (!voiceMetrics && !authorMetrics) return null;

  return (
    <section className="rounded-lg border border-border bg-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted/40 transition-colors"
        aria-label={
          open ? t("authorVoice.advancedMetricsHide") : t("authorVoice.advancedMetricsShow")
        }
      >
        <span className="flex items-center gap-1.5">
          {open ? (
            <ChevronDown className="w-3.5 h-3.5" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" />
          )}
          {t("authorVoice.advancedMetrics")}
        </span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4">
          <p
            className="flex items-start gap-1.5 text-[11px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/20 rounded-md px-2 py-1.5"
            role="note"
          >
            <Info className="w-3 h-3 flex-shrink-0 mt-0.5" />
            {t("authorVoice.metricsCaveat")}
          </p>

          {voiceMetrics && (
            <MetricGroup
              heading={t("authorVoice.voiceMetricsHeading")}
              metrics={voiceMetrics}
              t={t}
              kind="voice"
            />
          )}

          {authorMetrics && (
            <MetricGroup
              heading={t("authorVoice.authorMetricsHeading")}
              metrics={authorMetrics}
              t={t}
              kind="author"
            />
          )}
        </div>
      )}
    </section>
  );
}

interface MetricGroupProps {
  heading: string;
  metrics: VoiceMetrics | AuthorMetrics;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
  kind: "voice" | "author";
}

function MetricGroup({ heading, metrics, t, kind }: MetricGroupProps) {
  const rows =
    kind === "voice"
      ? voiceRows(metrics as VoiceMetrics, t)
      : authorRows(metrics as AuthorMetrics, t);
  if (rows.length === 0) return null;

  return (
    <div>
      <h5 className="text-xs text-muted-foreground mb-1">{heading}</h5>
      <dl className="grid grid-cols-1 gap-1.5 text-sm">{rows}</dl>
    </div>
  );
}
