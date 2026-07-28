"use client";

/**
 * AuthorVoiceChapterSelect — multi-select chapter list for ANAL-007.
 *
 * Defaults to ALL chapters selected (matches the backend "null chapter_ids =
 * all chapters" semantic). Surface a soft warning when the selection drops
 * below the 3-chapter minimum (does not block — ANAL-007 §"Minimum sample
 * size"). Select-all / clear actions for fast toggling.
 *
 * Extracted per RULE-04.
 */

import { AlertTriangle } from "lucide-react";
import type { ChapterSummary } from "@/types";

const MIN_CHAPTERS = 3;

interface AuthorVoiceChapterSelectProps {
  chapters: ChapterSummary[];
  selectedIds: Set<string>;
  onChange: (next: Set<string>) => void;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function AuthorVoiceChapterSelect({
  chapters,
  selectedIds,
  onChange,
  t,
}: AuthorVoiceChapterSelectProps) {
  const allSelected = selectedIds.size === chapters.length && chapters.length > 0;
  const belowMin = selectedIds.size < MIN_CHAPTERS;

  const toggle = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(next);
  };

  const selectAll = () => onChange(new Set(chapters.map((c) => c.id)));
  const clear = () => onChange(new Set());

  return (
    <section className="rounded-lg border border-border bg-card p-4 space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-xs text-muted-foreground font-medium">
          {t("authorVoice.chapterSelect")}
        </h4>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={selectAll}
            disabled={allSelected}
            className="text-[11px] text-violet-600 dark:text-violet-400 hover:underline disabled:opacity-40 disabled:no-underline"
          >
            {t("authorVoice.selectAll")}
          </button>
          <span className="text-[11px] text-muted-foreground">·</span>
          <button
            type="button"
            onClick={clear}
            disabled={selectedIds.size === 0}
            className="text-[11px] text-muted-foreground hover:underline disabled:opacity-40 disabled:no-underline"
          >
            {t("authorVoice.clearSelection")}
          </button>
        </div>
      </div>

      <p className="text-[11px] text-muted-foreground" aria-live="polite">
        {t("authorVoice.selectedCount", {
          count: selectedIds.size,
          total: chapters.length,
        })}
      </p>

      <ul className="max-h-48 overflow-y-auto space-y-0.5">
        {chapters.map((chapter) => {
          const checked = selectedIds.has(chapter.id);
          return (
            <li key={chapter.id}>
              <label className="flex items-center gap-2 py-1 px-1 rounded hover:bg-muted/40 cursor-pointer text-sm">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(chapter.id)}
                  aria-label={chapter.title}
                  className="h-3.5 w-3.5 rounded border-border"
                />
                <span className="truncate">{chapter.title}</span>
              </label>
            </li>
          );
        })}
      </ul>

      {belowMin && (
        <p
          className="flex items-start gap-1.5 text-[11px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/20 rounded-md px-2 py-1.5"
          role="note"
        >
          <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-0.5" />
          {t("authorVoice.minChaptersWarning")}
        </p>
      )}
    </section>
  );
}
