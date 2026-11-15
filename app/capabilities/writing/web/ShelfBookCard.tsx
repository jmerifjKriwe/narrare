/**
 * The grid's book card — the `shelf` draft's card geometry on the shell's
 * tokens: the cover at `shelf` size on its low pedestal, the title row with
 * the status pill (only when the book answered), the genre pill and the
 * blurb when the row carries them, the word pair in tabular figures with
 * the drafted progress, and the chapter/last-edited foot.
 *
 * The long-title rule is the states draft's (panel 4): the title wraps in
 * full, never an ellipsis — the whole name stays readable and accessible.
 * The cover's own three-line clamp is the cover system's contract.
 *
 * A book without a target keeps the honest neutral: the count alone, a —
 * where the percentage would stand, and an empty track. The quick menu
 * (Task 8) is real: its 28px trigger sits at the card's top-right and its
 * popover docks within the card, so the card is the positioning context.
 */

import type { Novel } from "@shell/lib/api/client";
import { BookCover } from "@shell/lib/cover/BookCover";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { formatRelative } from "@shell/lib/time";
import { Icon } from "@shell/ui/icons";

import { progress } from "./shelf";
import { ShelfQuickMenu } from "./ShelfQuickMenu";

/** The status vocabulary's pill faces — the server validates the values;
 *  an unknown one renders nothing rather than guessing a label. Draft wears
 *  the secondary container (the draft's own Entwurf pill), revision the
 *  raised rung with the second voice, final the sync badge's success pair.
 *  The filter popover's status facets read the same keys (Task 7). */
export const STATUS_PILL: Record<string, { key: MessageKey; className: string }> = {
  draft: {
    key: "writing.shelf.status.draft",
    className: "bg-secondary-container text-secondary-container-foreground",
  },
  revision: {
    key: "writing.shelf.status.revision",
    className: "bg-surface-container-high text-secondary",
  },
  final: {
    key: "writing.shelf.status.final",
    className: "border border-sync-badge-border bg-sync-badge text-sync-badge-ink",
  },
};

/** The writing-state pill — NULL is no answer, and no answer is no pill. */
export function StatusPill({ status }: { status: string | null | undefined }) {
  const t = useTranslation();
  if (status == null) return null;
  const pill = STATUS_PILL[status];
  if (pill === undefined) return null;
  return (
    <span
      className={`shrink-0 rounded-full px-2 py-0.5 text-eyebrow uppercase tracking-wide ${pill.className}`}
    >
      {t(pill.key)}
    </span>
  );
}

/** The drafted progress track. Without a target the track stands empty —
 *  no sliver, no invented percentage (the landing's honest neutral). */
export function ProgressTrack({
  wordCount,
  targetWords,
  trackClass,
}: {
  wordCount: number;
  targetWords: number | null | undefined;
  trackClass: string;
}) {
  const result = progress(wordCount, targetWords);
  return (
    <div className={`w-full overflow-hidden rounded-full ${trackClass}`}>
      {result !== null && result.width > 0 && (
        <div className="h-full rounded-full bg-cover-sepia" style={{ width: `${result.width}%` }} />
      )}
    </div>
  );
}

export function BookCard({ novel }: { novel: Novel }) {
  const t = useTranslation();
  const result = progress(novel.word_count, novel.target_words);
  return (
    <article className="group relative flex flex-col justify-between overflow-hidden rounded-xl border border-border bg-surface shadow-sm transition-all duration-200 hover:shadow-md">
      {/* The cover pedestal — the book object at shelf size. */}
      <div className="relative flex items-center justify-center overflow-hidden border-b border-rule bg-surface-container-low p-4">
        <div className="transition-transform duration-200 group-hover:-translate-y-1">
          <BookCover title={novel.title} genre={novel.genre} author={novel.author} size="shelf" />
        </div>
      </div>
      {/* The card body — the row's own facts. */}
      <div className="flex flex-1 flex-col justify-between space-y-3 p-4">
        <div>
          <div className="mb-1 flex items-start justify-between gap-1">
            {/* The states draft's long-title rule: wrap in full, no ellipsis. */}
            <h3 className="break-words text-emph text-foreground transition-colors group-hover:text-primary">
              {novel.title}
            </h3>
            <span className="flex shrink-0 flex-wrap items-center justify-end gap-1">
              {/* The archived marking — undrafted, the honest minimal: the
                  status pill's own shape from the row's archived_at presence
                  (Task 7's disclosure). The ink is the revision pill's own
                  passing pair on this surface — muted failed the AA bar at
                  eyebrow size in both halves (the review's finding). The
                  card is otherwise the same card; the archive never leads. */}
              {novel.archived_at != null && (
                <span className="shrink-0 rounded-full bg-surface-container-high px-2 py-0.5 text-eyebrow uppercase tracking-wide text-secondary">
                  {t("writing.shelf.archived")}
                </span>
              )}
              <StatusPill status={novel.status} />
            </span>
          </div>
          {novel.genre != null && (
            <span className="mt-1 inline-block rounded-full bg-surface-container-high px-2 py-0.5 text-eyebrow tracking-wide text-secondary">
              {novel.genre}
            </span>
          )}
          {novel.blurb != null && (
            <p className="mt-1.5 line-clamp-2 text-meta text-muted">{novel.blurb}</p>
          )}
        </div>
        <div className="space-y-2 pt-2">
          <div className="flex items-center justify-between gap-2 text-meta text-muted">
            <span className="tabular-nums">
              {novel.target_words != null
                ? t("writing.shelf.words.pair", { count: novel.word_count, target: novel.target_words })
                : t("writing.shelf.words.count", { count: novel.word_count })}
            </span>
            <span
              className={`text-label tabular-nums ${result !== null ? "font-semibold text-foreground" : "text-muted"}`}
            >
              {result !== null ? t("writing.shelf.card.percent", { percent: result.percent }) : "—"}
            </span>
          </div>
          <ProgressTrack
            wordCount={novel.word_count}
            targetWords={novel.target_words}
            trackClass="h-1 bg-surface-container"
          />
          <div className="flex items-center justify-between pt-1 text-meta text-muted">
            <span className="flex items-center gap-1">
              <Icon name="autoStories" size={14} />
              {t("writing.shelf.chapters", { count: novel.chapter_count })}
            </span>
            <span>{formatRelative(novel.updated_at)}</span>
          </div>
        </div>
      </div>
      {/* The quick menu — its trigger at the card's top-right, its popover
          docked within the card (Task 8). */}
      <ShelfQuickMenu novel={novel} />
    </article>
  );
}
