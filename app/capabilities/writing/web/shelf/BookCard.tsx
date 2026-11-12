import { useState } from "react";
import { Link } from "@tanstack/react-router";

import { useTranslation } from "@shell/lib/i18n";
import { formatRelative } from "@shell/lib/time";
import { Cover } from "@shell/ui/Cover";
import { ActionMenu } from "@shell/ui/Menu";
import { Icon } from "@shell/ui/icons";
import { NovelDetailsDialog, NovelDeleteDialog } from "./NovelDialogs";
import { ExportNovelDialog } from "../InterchangeDialogs";
import type { Novel } from "@shell/lib/api/client";

/**
 * The drafted grid card (`screens/library/shelf.html`): the cover in its
 * panel, the quick menu at the panel's corner, and the body — title,
 * status pill, blurb, words, chapters and the touch time — as one press
 * target. The title wraps (the states screen's long-title answer: no
 * ellipsis, no data loss — the full string is the link's accessible name,
 * and `break-words` keeps an unbreakable token inside its box).
 *
 * The card's deeds are the app's own — details, export, delete — behind
 * the drafted more_horiz trigger; the shelf stays a grid of faces.
 */

/** The book's face on the grid. */
export function BookCard({ novel }: { novel: Novel }) {
  const t = useTranslation();
  // The card's deeds open their own dialogs at the card's own scope, so
  // each book's dialog holds its book and no other surface can open one
  // book's dialog over another's card.
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  return (
    <li
      data-shelf-card
      className="group relative flex flex-col justify-between overflow-hidden rounded-[var(--radius-surface)] bg-card shadow-[var(--shadow-card)]"
    >
      <div className="relative flex items-center justify-center overflow-hidden bg-surface-container-low p-4">
        <div className="transition-transform duration-200 group-hover:-translate-y-1">
          <Cover title={novel.title} size="card" genre={novel.genre} language={novel.language} />
        </div>
        <div className="absolute right-2 top-2">
          <ActionMenu
            triggerAriaLabel={t("novels.actionsFor", { title: novel.title })}
            triggerIcon="moreHoriz"
            items={[
              {
                id: "details",
                label: t("novels.details"),
                onSelect: () => setDetailsOpen(true),
              },
              {
                id: "export",
                label: t("shelf.export"),
                onSelect: () => setExportOpen(true),
              },
              {
                id: "delete",
                label: t("novels.delete"),
                onSelect: () => setDeleteOpen(true),
              },
            ]}
          />
        </div>
      </div>
      <Link
        to="/novels/$id"
        params={{ id: novel.id }}
        className="flex flex-1 flex-col justify-between gap-3 p-4 no-underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent"
      >
        <div className="min-w-0">
          <div className="mb-1 flex items-start justify-between gap-1">
            <h3
              data-shelf-title
              className="min-w-0 break-words text-title text-foreground transition-colors group-hover:text-primary"
            >
              {novel.title}
            </h3>
            {/* Interim: no status field exists; every book wears the
             * draft's default pill until one does.
             * Missing data: the per-book status field.
             * Follow-up: render the real status (index issue at Task 11). */}
            <span className="shrink-0 rounded-full bg-secondary-container px-2 py-0.5 text-eyebrow uppercase text-secondary-container-foreground">
              {t("shelf.statusDraft")}
            </span>
          </div>
          {novel.blurb ? (
            <p className="line-clamp-2 text-meta text-muted">{novel.blurb}</p>
          ) : null}
        </div>
        <div className="space-y-2 pt-2">
          {/* Interim: no per-book target exists, so the drafted
           * "x / y Wörter" row and the card's progress bar are absent —
           * the words alone are the row's real truth, and no percentage is
           * ever implied. The E2E pins this: words, never percentages.
           * Missing data: per-book word target.
           * Follow-up: render the target pair, percent and bar (index
           * issue at Task 11). */}
          <div className="text-meta text-muted tabular-nums">
            {t("shelf.card.words", { count: novel.word_count })}
          </div>
          <div className="flex items-center justify-between pt-1 text-meta text-muted">
            <span className="flex items-center gap-1">
              <Icon name="autoStories" />
              {t("shelf.card.chapters", { count: novel.chapter_count })}
            </span>
            <span>{formatRelative(novel.updated_at)}</span>
          </div>
        </div>
      </Link>
      <NovelDetailsDialog novel={novel} open={detailsOpen} onOpenChange={setDetailsOpen} />
      <NovelDeleteDialog novel={novel} open={deleteOpen} onOpenChange={setDeleteOpen} />
      <ExportNovelDialog novel={novel} isOpen={exportOpen} onOpenChange={setExportOpen} />
    </li>
  );
}
