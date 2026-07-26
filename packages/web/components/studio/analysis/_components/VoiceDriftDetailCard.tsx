"use client";

/**
 * VoiceDriftDetailCard — β-style per-character detail (ANAL-009 Layout γ drill-in).
 *
 * Shown inline when a heatmap row is expanded. Renders the per-chapter match
 * trend (sparkline + chapter strip), the jump-point list, the agent's reasoning
 * quote (the qualitative half — ADR-021 hybrid tier), and a collapsible
 * per-chapter-notes section. Mirrors the approved mockup's `.card` block.
 *
 * Every field is a display-only report artifact — drift analysis is read-only
 * (ADR-073 Decision 5); nothing here is persisted.
 *
 * @module VoiceDriftDetailCard
 */

import { useState } from "react";
import type { VoiceDriftCharacterResult } from "@/lib/api/voice-drift-stream";
import { VoiceDriftDetailNotes } from "./VoiceDriftDetailNotes";
import { VoiceDriftJumpList } from "./VoiceDriftJumpList";
import { VoiceDriftSparkline } from "./VoiceDriftSparkline";
import { composeClassification, DRIFT_BANDS, formatMatchPercent } from "./voice-drift-bands";

interface VoiceDriftDetailCardProps {
  result: VoiceDriftCharacterResult;
  /** chapter_id → ordinal label (e.g. "Ch3"). Built by the owning overview. */
  chapterLabel: (chapterId: string) => string;
  /** scoped `analysis` translator. */
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function VoiceDriftDetailCard({ result, chapterLabel, t }: VoiceDriftDetailCardProps) {
  const [notesOpen, setNotesOpen] = useState(false);
  const { character_name: name, trend, jumps, overall_match_score, overall_band, drift } = result;

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
      aria-label={name || t("voiceDrift.title")}
    >
      {/* Header: name + chapters analyzed + classification + overall % */}
      <header className="mb-4 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h4 className="font-serif text-xl font-semibold leading-tight text-foreground">
            {name || "\u2014"}
          </h4>
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
            {t("voiceDrift.chaptersAnalyzed", { count: trend.length })}
          </span>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          {classification && (
            <span
              className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                overallBandMeta?.badge ?? "border-border bg-muted text-muted-foreground"
              }`}
            >
              {t(`voiceDrift.classification.${classification}`)}
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
                {t("voiceDrift.matchToProfile")}
              </span>
            </div>
          )}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4">
        {/* Trend block: sparkline + chapter strip */}
        <div className="flex flex-col gap-2">
          <div className="flex items-end justify-between gap-3">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              {t("voiceDrift.trendLabel")}
            </span>
          </div>
          <VoiceDriftSparkline
            trend={trend}
            jumps={jumps}
            ariaLabel={t("voiceDrift.trendAria", { name: name || "" })}
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
            {t("voiceDrift.agentReasoning")}
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
          {t(notesOpen ? "voiceDrift.hideNotes" : "voiceDrift.viewNotes")}
        </button>
      )}
      {notesOpen && <VoiceDriftDetailNotes result={result} chapterLabel={chapterLabel} t={t} />}
    </article>
  );
}

/** Coloured chapter strip under the sparkline (pip + score + Ch label per chapter). */
function ChapterStrip({
  trend,
  chapterLabel,
}: {
  trend: VoiceDriftCharacterResult["trend"];
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
