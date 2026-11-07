/**
 * The export trace's one comparison (§5): the book's `last_exported_at`
 * against `novel.updated_at`, which D8 makes the whole canon's truth —
 * every write the archive carries advances that stamp, so the two instants
 * alone decide whether a backup holds the book.
 *
 * Pure on purpose: no clock inside, `now` is a parameter, so the tests pin
 * the verdicts and the callers choose the moment. The stamps are compared
 * as parsed instants, never as strings — two ISO strings with different
 * timezone offsets do not order as their moments do.
 */
export type ExportAge =
  | { kind: "never" }
  | { kind: "fresh" }
  | { kind: "stale"; days: number };

const DAY_MS = 86_400_000;

/** Whole days since an instant, floored at zero — a stamp in the future
 *  reads as today, never as a negative age. */
function daysSince(timestamp: number, now: number): number {
  return Math.max(0, Math.floor((now - timestamp) / DAY_MS));
}

/**
 * The verdict for a delete dialog's export line: `never` when no export
 * exists, `fresh` when the export followed the last change (equal instants
 * included — an export landing on the change's own moment still holds it),
 * `stale` with the backup's own age in whole days when a change has no
 * export over it. The age is the export's, not the change's: an hour-old
 * edit over a ten-day-old backup warns about the ten days.
 */
export function exportAge(
  lastExportedAt: string | null,
  changedAt: string,
  now: Date,
): ExportAge {
  if (lastExportedAt === null) return { kind: "never" };
  const exported = Date.parse(lastExportedAt);
  if (Date.parse(changedAt) <= exported) return { kind: "fresh" };
  return { kind: "stale", days: daysSince(exported, now.getTime()) };
}
