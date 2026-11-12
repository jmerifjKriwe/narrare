import { Link } from "@tanstack/react-router";

import { useTranslation } from "@shell/lib/i18n";
import { formatRelative } from "@shell/lib/time";
import { Cover } from "@shell/ui/Cover";
import type { Novel } from "@shell/lib/api/client";

/**
 * The shelf's dense view — the row composition the states screen draws for
 * a growing library (`screens/library/shelf-states.html`, panel 3): a
 * compact row per book, two columns wide, the cover's thumbnail beside the
 * title, the words, the pill and the touch time. The rows carry the same
 * facts as the cards and open the same book; what changes is only the
 * density. It is the toggle's second view, the one a growing library
 * reaches for.
 */

/** One book as a compact row. */
function BookRow({ novel }: { novel: Novel }) {
  const t = useTranslation();
  return (
    <li data-shelf-row className="min-w-0">
      <Link
        to="/novels/$id"
        params={{ id: novel.id }}
        className="flex items-center gap-2 rounded-[var(--radius-sm)] border border-border bg-card p-2 no-underline transition-colors hover:border-primary focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent"
      >
        <Cover title={novel.title} genre={novel.genre} language={novel.language} />
        <span className="min-w-0 flex-1">
          <span
            data-shelf-title
            className="block truncate text-label font-semibold text-foreground"
          >
            {novel.title}
          </span>
          <span className="mt-0.5 flex flex-wrap items-center gap-2 text-meta text-muted">
            <span className="tabular-nums">
              {t("shelf.card.words", { count: novel.word_count })}
            </span>
            {/* Interim: no status field exists; the draft's default pill
             * until one does — the same neutral the cards wear.
             * Missing data: the per-book status field.
             * Follow-up: render the real status (index issue at Task 11). */}
            <span className="rounded-full bg-secondary-container px-2 py-0.5 text-eyebrow uppercase text-secondary-container-foreground">
              {t("shelf.statusDraft")}
            </span>
            <span>{formatRelative(novel.updated_at)}</span>
          </span>
        </span>
      </Link>
    </li>
  );
}

/** The dense rows: two columns from the tablet up, the drafted grid's gap. */
export function BookList({ novels }: { novels: Novel[] }) {
  return (
    <ul className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
      {novels.map((novel) => (
        <BookRow key={novel.id} novel={novel} />
      ))}
    </ul>
  );
}
