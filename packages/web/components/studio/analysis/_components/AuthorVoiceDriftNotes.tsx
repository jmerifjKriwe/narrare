"use client";

/**
 * AuthorVoiceDriftNotes — collapsible per-chapter notes + suggested-attention
 * chapter list for the author-voice-drift narrator trend (ANAL-009 Phase 2B).
 *
 * Sibling of {@link ./VoiceDriftDetailNotes} but takes the shared
 * {@link VoiceDriftResult} directly (the narrator trend carries no character
 * identity — author voice is one narrator per novel). Extracted from the trend
 * card per RULE-04 (file-size limit).
 *
 * @module AuthorVoiceDriftNotes
 */

import type { VoiceDriftResult } from "@/lib/api/voice-drift-stream";

interface AuthorVoiceDriftNotesProps {
  /** The agent's qualitative classification (reused Phase 1 shape). */
  drift: VoiceDriftResult;
  /** chapter_id → ordinal label (e.g. "Ch3"). Built by the owning trend card. */
  chapterLabel: (chapterId: string) => string;
  /** scoped `analysis` translator. */
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

/** Collapsible per-chapter notes + suggested-attention chapter list. */
export function AuthorVoiceDriftNotes({ drift, chapterLabel, t }: AuthorVoiceDriftNotesProps) {
  return (
    <div className="mt-3 space-y-3 rounded-lg border border-border bg-muted/20 p-3">
      {drift.per_chapter_notes.length > 0 && (
        <dl className="space-y-2">
          <dt className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {t("authorVoiceDrift.perChapterNotes")}
          </dt>
          {drift.per_chapter_notes.map((note) => (
            <div key={note.chapter_id} className="flex gap-2 text-sm">
              <span className="flex-shrink-0 font-medium tabular-nums text-muted-foreground">
                {chapterLabel(note.chapter_id)}
              </span>
              <dd className="text-muted-foreground">{note.note}</dd>
            </div>
          ))}
        </dl>
      )}
      {drift.suggested_attention.length > 0 && (
        <div>
          <dt className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {t("authorVoiceDrift.suggestedAttention")}
          </dt>
          <dd className="mt-1 flex flex-wrap gap-1.5">
            {drift.suggested_attention.map((chapterId) => (
              <span
                key={chapterId}
                className="inline-flex items-center rounded-full border border-orange-300 bg-orange-500/10 px-2 py-0.5 text-[11px] tabular-nums text-orange-700 dark:border-orange-700 dark:text-orange-300"
              >
                {chapterLabel(chapterId)}
              </span>
            ))}
          </dd>
        </div>
      )}
    </div>
  );
}
