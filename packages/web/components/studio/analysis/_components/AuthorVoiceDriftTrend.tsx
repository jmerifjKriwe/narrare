"use client";

/**
 * AuthorVoiceDriftTrend — the always-visible single narrator drift trend
 * (ANAL-009 Phase 2B).
 *
 * Author voice is ONE narrator per novel, so this card renders the full detail
 * directly (no per-character heatmap + expand like Phase 1's VoiceDriftDetailCard):
 * the per-chapter match sparkline (signal i) + jump markers (signal iii) + the
 * overall classification badge + the agent's qualitative reasoning quote
 * (ADR-021 hybrid tier) + a collapsible per-chapter-notes section.
 *
 * Reuses the shared presentation pieces — {@link ./VoiceDriftSparkline},
 * {@link ./VoiceDriftJumpList}, and the band metadata in
 * {@link ./voice-drift-bands} — which operate on the locked Core shapes
 * (`TrendPoint` / `JumpPoint`) reused across both phases.
 *
 * Chapters are labelled by their ordinal position in the trend (Ch1, Ch2…)
 * since the backend carries only chapter ids. Every field is a display-only
 * report artifact — drift analysis is read-only (ADR-073 Decision 5).
 *
 * @module AuthorVoiceDriftTrend
 */

import { useMemo, useState } from "react";
import type { AuthorVoiceDriftResult } from "@/lib/api/author-voice-drift-stream";
import { AuthorVoiceDriftNotes } from "./AuthorVoiceDriftNotes";
import { VoiceDriftJumpList } from "./VoiceDriftJumpList";
import { VoiceDriftSparkline } from "./VoiceDriftSparkline";
import { composeClassification, DRIFT_BANDS, formatMatchPercent } from "./voice-drift-bands";

interface AuthorVoiceDriftTrendProps {
  /** The singular narrator drift result. */
  result: AuthorVoiceDriftResult;
  /** scoped `analysis` translator. */
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function AuthorVoiceDriftTrend({ result, t }: AuthorVoiceDriftTrendProps) {
  const [notesOpen, setNotesOpen] = useState(false);
  const { trend, jumps, overall_match_score, overall_band, drift } = result;

  // The trend is already in chapter order; label by ordinal position (Ch1, Ch2…).
  const chapterLabel = useMemo(() => {
    const ids = trend.map((p) => p.chapter_id);
    return (chapterId: string): string => {
      const idx = ids.indexOf(chapterId);
      return idx >= 0 ? `Ch${idx + 1}` : chapterId;
    };
  }, [trend]);

  const classification = composeClassification(overall_band, drift.drift_type);
  const overallPct = formatMatchPercent(overall_match_score);
  const overallBandMeta = overall_band ? DRIFT_BANDS[overall_band] : null;
  const reasons = drift.longitudinal_reasons;
  const attention = drift.suggested_attention;

  return (
    <article
      className={`rounded-xl border border-border bg-card p-4 sm:p-5 ${
        overall_band ? `border-l-4 ${overallBandMeta?.cellBorder}` : ""
      }`}
      aria-label={t("authorVoiceDrift.title")}
    >
      {/* Header: title + chapters analyzed + classification + overall % */}
      <header className="mb-4 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h4 className="font-serif text-xl font-semibold leading-tight text-foreground">
            {t("authorVoiceDrift.narrator")}
          </h4>
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
            {t("authorVoiceDrift.chaptersAnalyzed", { count: trend.length })}
          </span>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          {classification && (
            <span
              className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                overallBandMeta?.badge ?? "border-border bg-muted text-muted-foreground"
              }`}
            >
              {t(`authorVoiceDrift.classification.${classification}`)}
            </span>
          )}
          {overallPct && (
            <div className="text-right">
              <span
                className={`font-serif text-2xl font-semibold tabular-nums ${overallBandMeta?.text ?? ""}`}
              >
                {overallPct}
              </span>
              <span className="mt-0.5 block text-[9px] uppercase tracking-wider text-muted-foreground">
                {t("authorVoiceDrift.matchToProfile")}
              </span>
            </div>
          )}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4">
        {/* Trend block: sparkline + chapter strip */}
        <div className="flex flex-col gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {t("authorVoiceDrift.trendLabel")}
          </span>
          <VoiceDriftSparkline
            trend={trend}
            jumps={jumps}
            ariaLabel={t("authorVoiceDrift.trendAria")}
          />
          <ChapterStrip trend={trend} chapterLabel={chapterLabel} />
        </div>

        {/* Jump points */}
        <VoiceDriftJumpList jumps={jumps} chapterLabel={chapterLabel} t={t} />
      </div>

      {/* Agent reasoning quote (the qualitative half — ADR-021). */}
      {reasons.length > 0 && (
        <blockquote className="mt-4 rounded-r-lg border-l-2 border-orange-400/60 bg-muted/30 py-2 pl-3 pr-3 dark:border-orange-500/40">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {t("authorVoiceDrift.agentReasoning")}
          </span>
          <p className="mt-1 font-serif text-sm italic leading-relaxed text-muted-foreground">
            {reasons.join(" ")}
          </p>
        </blockquote>
      )}

      {/* Collapsible per-chapter notes + suggested attention. */}
      {(drift.per_chapter_notes.length > 0 || attention.length > 0) && (
        <button
          type="button"
          onClick={() => setNotesOpen((v) => !v)}
          className="mt-3 self-start rounded-md border border-border bg-transparent px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted"
          aria-expanded={notesOpen}
        >
          {t(notesOpen ? "authorVoiceDrift.hideNotes" : "authorVoiceDrift.viewNotes")}
        </button>
      )}
      {notesOpen && <AuthorVoiceDriftNotes drift={drift} chapterLabel={chapterLabel} t={t} />}
    </article>
  );
}

/** Coloured chapter strip under the sparkline (pip + score + Ch label per chapter). */
function ChapterStrip({
  trend,
  chapterLabel,
}: {
  trend: AuthorVoiceDriftResult["trend"];
  chapterLabel: (chapterId: string) => string;
}) {
  return (
    <div className="flex gap-1.5">
      {trend.map((p) => {
        const meta = DRIFT_BANDS[p.band];
        return (
          <div key={p.chapter_id} className="flex min-w-0 flex-1 flex-col items-center gap-1">
            <span className={`h-1.5 w-full rounded-sm ${meta.cellBg}`} aria-hidden />
            <span className="tabular-nums text-[10px] text-muted-foreground">
              {Math.round(p.match_subscore)}
            </span>
            <span className="text-[9px] tracking-tight text-muted-foreground/70">
              {chapterLabel(p.chapter_id)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
