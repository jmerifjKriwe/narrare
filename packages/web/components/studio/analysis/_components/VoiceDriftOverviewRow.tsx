/**
 * VoiceDriftOverviewRow — one character row in the Layout γ heatmap (ANAL-009).
 *
 * Renders the character name (a toggle button that expands the detail card),
 * one drift-band cell per chapter in the whole-novel column set (with ⚡ jump
 * markers on jump target chapters), the classification badge, and the overall
 * match %. Chapters where the character is silent render an empty cell
 * (RULE-11 — no artificial zeros).
 *
 * Extracted from {@link ./VoiceDriftOverview} per RULE-04 (file-size limit).
 *
 * @module VoiceDriftOverviewRow
 */

import type { VoiceDriftCharacterResult } from "@/lib/api/voice-drift-stream";
import { composeClassification, DRIFT_BANDS, formatMatchPercent } from "./voice-drift-bands";

interface VoiceDriftOverviewRowProps {
  result: VoiceDriftCharacterResult;
  /** Whole-novel chapter column set (union across all characters). */
  chapterIds: string[];
  /** chapter_id → ordinal label (e.g. "Ch3"). */
  chapterLabel: (chapterId: string) => string;
  isExpanded: boolean;
  /** True when another row is expanded (this row dims). */
  isDimmed: boolean;
  onToggle: () => void;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function VoiceDriftOverviewRow({
  result,
  chapterIds,
  chapterLabel,
  isExpanded,
  isDimmed,
  onToggle,
  t,
}: VoiceDriftOverviewRowProps) {
  const { character_name: name, trend, jumps, overall_match_score, overall_band, drift } = result;
  const trendByChapter = new Map(trend.map((p) => [p.chapter_id, p]));
  const jumpTargets = new Set(jumps.map((j) => j.to_chapter_id));
  const classification = composeClassification(overall_band, drift.drift_type);
  const overallPct = formatMatchPercent(overall_match_score);
  const overallMeta = overall_band ? DRIFT_BANDS[overall_band] : null;

  return (
    <tr className={`${isDimmed ? "opacity-60" : ""} ${isExpanded ? "bg-accent/40" : ""}`}>
      <td className="py-1 text-left">
        <button
          type="button"
          onClick={onToggle}
          className="flex items-center gap-1.5 font-serif text-sm text-foreground hover:text-violet-600 dark:hover:text-violet-400"
          aria-expanded={isExpanded}
          aria-label={t("voiceDrift.toggleRowAria", { name: name || "" })}
        >
          {isExpanded && <span className="text-violet-500">{"\u25BE"}</span>}
          {name || "\u2014"}
        </button>
      </td>
      {chapterIds.map((chapterId) => (
        <OverviewCell
          key={chapterId}
          chapterId={chapterId}
          point={trendByChapter.get(chapterId)}
          hasJump={jumpTargets.has(chapterId)}
          chapterLabel={chapterLabel}
          t={t}
        />
      ))}
      <td className="py-1 pl-2 text-left">
        {classification && (
          <span
            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${overallMeta?.badge ?? "border-border bg-muted text-muted-foreground"}`}
          >
            {t(`voiceDrift.classification.${classification}`)}
          </span>
        )}
      </td>
      <td className="py-1 pl-2 text-left">
        {overallPct && (
          <span
            className={`font-serif text-lg font-semibold tabular-nums ${overallMeta?.text ?? ""}`}
          >
            {overallPct}
          </span>
        )}
      </td>
    </tr>
  );
}

/** One heatmap cell — drift band + match % (+ ⚡ jump marker). Empty when silent. */
function OverviewCell({
  chapterId,
  point,
  hasJump,
  chapterLabel,
  t,
}: {
  chapterId: string;
  point: VoiceDriftCharacterResult["trend"][number] | undefined;
  hasJump: boolean;
  chapterLabel: (chapterId: string) => string;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}) {
  if (!point) {
    return (
      <td className="text-center">
        <span className="inline-block h-12 w-11" title={t("voiceDrift.silentChapter")} />
      </td>
    );
  }
  const meta = DRIFT_BANDS[point.band];
  const title = `${chapterLabel(chapterId)} · ${Math.round(point.match_subscore)} · ${t(`voiceDrift.band.${meta.label}`)}`;
  return (
    <td className="text-center">
      <div
        className={`relative flex h-12 w-11 flex-col items-center justify-center gap-px rounded-lg border ${meta.cellBg} ${meta.cellBorder}`}
        title={title}
      >
        {hasJump && (
          <span
            className="absolute -left-2 top-1/2 z-10 grid h-4 w-4 -translate-y-1/2 place-items-center rounded-full bg-amber-500/20 text-[10px] text-amber-500 ring-1 ring-amber-500/40"
            title={t("voiceDrift.jumpTooltip", { chapter: chapterLabel(chapterId) })}
          >
            {"\u26A1"}
          </span>
        )}
        <span className={`text-[13px] leading-none ${meta.text}`} aria-hidden>
          {meta.symbol}
        </span>
        <span className="text-[10px] tabular-nums text-muted-foreground">
          {Math.round(point.match_subscore)}
        </span>
      </div>
    </td>
  );
}
