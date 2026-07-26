/**
 * VoiceDriftJumpList — the adjacent-chapter jump-point list (ANAL-009 signal iii).
 *
 * Renders each jump as `⚡ Ch{n} → Ch{m} — <metric>` (the metric that shifted),
 * mirroring the approved mockup's `.jumps` block. Localises *where* drift began.
 *
 * Chapters are labelled by their ordinal position within the trend (Ch1, Ch2…)
 * since the backend carries only chapter ids (no titles on the SSE result);
 * the raw chapter id is exposed via `title` for hover/accessibility.
 *
 * @module VoiceDriftJumpList
 */

import type { JumpPoint } from "@/lib/api/voice-drift-stream";

interface VoiceDriftJumpListProps {
  jumps: JumpPoint[];
  /** chapter_id → ordinal label (e.g. "Ch3"). Built by the owning card. */
  chapterLabel: (chapterId: string) => string;
  /** scoped `analysis` translator. */
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function VoiceDriftJumpList({ jumps, chapterLabel, t }: VoiceDriftJumpListProps) {
  if (jumps.length === 0) {
    return <p className="mt-2 text-sm italic text-muted-foreground">{t("voiceDrift.noJumps")}</p>;
  }

  return (
    <div>
      <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {t("voiceDrift.jumpPoints")}
      </h4>
      <ul className="mt-2 flex flex-col gap-2">
        {jumps.map((jump) => {
          const metrics = jump.jumped_metrics.join(", ");
          return (
            <li
              key={`${jump.from_chapter_id}-${jump.to_chapter_id}`}
              className="flex items-center gap-2 text-sm text-muted-foreground"
            >
              <span aria-hidden className="text-amber-500">
                {"\u26A1"}
              </span>
              <span>
                <span className="tabular-nums">{chapterLabel(jump.from_chapter_id)}</span>
                {" \u2192 "}
                <span className="tabular-nums">{chapterLabel(jump.to_chapter_id)}</span>
                {" \u2014 "}
                <em className="font-serif italic text-foreground">{metrics}</em>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
