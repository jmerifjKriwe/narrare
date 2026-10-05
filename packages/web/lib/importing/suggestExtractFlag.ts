// sessionStorage flag contract for the post-import extraction suggestion
// (F2 T8, ADR-092 spec §8.1, D9a). Written by the wizard's successful import
// commit, consumed by the SidebarChapterList banner. Key + payload live in ONE
// module so writer and readers cannot drift (same single-source rule as the
// `narrare:importFailed:{novel_id}` flag).

import type { ImportCommitChapterInfo } from "@/types";

/** Payload of `narrare:importSuggestExtract:{novel_id}` — self-contained, so the sidebar CTA needs no extra fetch. */
export interface ImportSuggestion {
  readonly chapterIds: readonly string[];
  readonly wordCount: number;
}

const KEY_PREFIX = "narrare:importSuggestExtract:";
/**
 * Payload bound: the flag is a SUGGESTION, not the job seed of record — the
 * panel later starts over exactly the ids the user accepted. 100 ids keep the
 * sessionStorage entry small even though the engine accepts up to 200.
 */
const MAX_CHAPTER_IDS = 100;

export function suggestExtractKey(novelId: string): string {
  return `${KEY_PREFIX}${novelId}`;
}

/**
 * Store the suggestion after a successful import commit. Bounded at
 * MAX_CHAPTER_IDS ids with the word count summed over the SAME bounded list
 * (the cost line must describe the chapters actually suggested). No-op for an
 * empty commit — there is nothing to suggest extracting.
 */
export function writeSuggestExtractFlag(
  novelId: string,
  chapters: readonly ImportCommitChapterInfo[],
): void {
  const bounded = chapters.slice(0, MAX_CHAPTER_IDS);
  if (bounded.length === 0) return;
  sessionStorage.setItem(
    suggestExtractKey(novelId),
    JSON.stringify({
      chapter_ids: bounded.map((c) => c.id),
      word_count: bounded.reduce((sum, c) => sum + c.word_count, 0),
    }),
  );
}

/**
 * Defensive read: any malformed entry (corrupt JSON, wrong shape, empty id
 * list) degrades to "no suggestion" — same posture as the failed-flag read.
 */
export function readSuggestExtractFlag(novelId: string): ImportSuggestion | null {
  const raw = sessionStorage.getItem(suggestExtractKey(novelId));
  if (raw === null) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const record = parsed as { chapter_ids?: unknown; word_count?: unknown };
    if (!Array.isArray(record.chapter_ids)) return null;
    const chapterIds = record.chapter_ids.filter((id): id is string => typeof id === "string");
    if (chapterIds.length === 0) return null;
    return {
      chapterIds,
      wordCount: typeof record.word_count === "number" ? record.word_count : 0,
    };
  } catch {
    return null;
  }
}

export function clearSuggestExtractFlag(novelId: string): void {
  sessionStorage.removeItem(suggestExtractKey(novelId));
}
