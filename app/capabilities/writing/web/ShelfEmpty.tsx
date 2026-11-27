/**
 * The unpopulated shelf — the `shelf-empty` draft's panel: the blank book
 * object under two soft glows, the du-tone invitation, and the two doors
 * (new book → Task 9's dialog, real; import → the import wave, honestly
 * disabled with the drafted note). The metrics strip above answers zero.
 *
 * The blank book is the draft's own object for the *absence* of a book —
 * ported as a static decoration (aria-hidden), not a BookCover: the cover
 * system speaks for real novels, and this one holds none. Its hover lift
 * is dropped (a hover would imply a clickability it lacks, the landing's
 * workroom precedent); its white rim is the cover system's dark-half rim,
 * transparent in light. The draft's „0 / 750" banner numbers are mock —
 * the shared banner placeholder stands neutral instead.
 *
 * The archive door (Task 8) is real — the `shelf-quick-menu` draft's
 * empty-shelf entry, a ghost text link that opens the list with
 * `include_archived` on, closing Task 7's carried gap (the archive was
 * unreachable from an empty active shelf). Once the archive has been asked
 * and holds nothing, the draft's own honest line answers („Keine ruhenden
 * Entwürfe") — never a dead door, never an invented count.
 */

import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";
import type { MouseEvent } from "react";

/** The shell's focus ring on the one live control the empty shelf offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The cover system's dark rim (BookCover's RIM): transparent in light. */
const RIM = "border-y border-r [border-color:light-dark(transparent,rgba(255,255,255,0.08))]";

/** The blank book — the draft's sepia object with its ribbon and seal. */
function BlankBook() {
  const t = useTranslation();
  return (
    <div
      aria-hidden="true"
      className={`relative my-6 flex h-72 w-48 shrink-0 flex-col justify-between overflow-hidden rounded-l-sm rounded-r-lg bg-cover-sepia p-5 text-cover-sepia-ink shadow-2xl ${RIM}`}
    >
      {/* The spine crease and the ribbon, the draft's own geometry. */}
      <div className="absolute inset-y-0 left-0 w-4 bg-[linear-gradient(90deg,rgba(0,0,0,0.45)_0%,rgba(255,255,255,0.15)_50%,transparent_100%)]" />
      <div className="absolute right-8 top-0 h-14 w-4 rounded-b-sm border-b border-primary/20 bg-secondary-container shadow-md" />
      <div className="relative z-10 pl-2 text-left">
        <span className="mb-1 block text-[9px] uppercase tracking-widest opacity-70">
          {t("writing.shelf.empty.book.eyebrow")}
        </span>
        <div className="mb-3 h-0.5 w-8 bg-focus/80" />
        <span className="block text-meta italic opacity-70">{t("writing.shelf.empty.book.line")}</span>
      </div>
      <div className="relative z-10 my-auto flex flex-col items-center justify-center self-center pl-2 opacity-85">
        <div className="flex h-14 w-14 items-center justify-center rounded-full border border-dashed border-current/70">
          <Icon name="autoStories" size={28} />
        </div>
        <span className="mt-2 text-eyebrow uppercase tracking-widest">
          {t("writing.shelf.empty.book.leaf")}
        </span>
      </div>
      <div className="relative z-10 flex items-center justify-between pl-2 opacity-70">
        <span className="text-meta">{t("writing.shelf.empty.book.foot")}</span>
        <Icon name="editNote" size={16} />
      </div>
    </div>
  );
}

export function ShelfEmpty({
  noteId,
  archiveIncluded,
  onBrowseArchive,
  onNewBook,
}: {
  noteId: string;
  archiveIncluded: boolean;
  onBrowseArchive: () => void;
  onNewBook: (event: MouseEvent<HTMLButtonElement>) => void;
}) {
  const t = useTranslation();
  return (
    <section className="relative flex flex-col items-center justify-center overflow-hidden rounded-xl border border-rule bg-surface-container-low p-6 text-center shadow-sm lg:p-8">
      {/* The two soft glows — the draft's ambient depth, token pigments. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-24 -top-24 h-80 w-80 rounded-full bg-cover-sepia opacity-5 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-24 -right-24 h-80 w-80 rounded-full bg-primary opacity-5 blur-3xl"
      />
      <BlankBook />
      <div className="relative z-10 max-w-xl space-y-3">
        <h2 className={`${SERIF} text-3xl font-semibold tracking-tight text-primary`}>
          {t("writing.shelf.empty.title")}
        </h2>
        <p className={`${SERIF} text-body italic leading-relaxed text-muted`}>
          {t("writing.shelf.empty.body")}
        </p>
      </div>
      <div className="relative z-10 flex flex-wrap items-center justify-center gap-3 pt-4">
        {/* Task 9's dialog: the empty shelf's own door into the same modal
            the top bar opens — the page remembers it as the focus return. */}
        <button
          type="button"
          onClick={onNewBook}
          className={`inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-5 text-label font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-95 ${FOCUS}`}
        >
          <Icon name="plus" size={18} />
          <span>{t("writing.shelf.newBook")}</span>
        </button>
        {/* The import door stays disabled; its future-facing note is shared
            with the adjacent live new-book CTA. */}
        <button
          type="button"
          disabled
          aria-describedby={noteId}
          className="inline-flex h-10 cursor-not-allowed items-center gap-2 rounded-lg border border-rule bg-surface px-4 text-label text-foreground opacity-50 shadow-sm"
        >
          <span className="text-area-writing">
            <Icon name="uploadFile" size={18} />
          </span>
          <span>{t("writing.shelf.empty.import")}</span>
        </button>
      </div>
      <div className="relative z-10 pt-4">
        <p className="flex items-center justify-center gap-1.5 text-meta text-muted">
          <Icon name="document" size={15} />
          <span>{t("writing.shelf.empty.formats")}</span>
        </p>
        <p id={noteId} className="mt-2 text-meta text-muted">
          {t("writing.shelf.comingSoon")}
        </p>
      </div>
      {/* The archive door — real, the draft's ghost link. With the archive
          already asked and empty, the draft's own honest line stands. */}
      <div className="relative z-10 pt-4">
        {archiveIncluded ? (
          <p className="flex items-center justify-center gap-1.5 text-meta text-muted">
            <Icon name="archive" size={15} />
            <span>{t("writing.shelf.empty.archiveEmpty")}</span>
          </p>
        ) : (
          <button
            type="button"
            onClick={onBrowseArchive}
            className={`inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-label font-medium text-primary transition-colors hover:text-foreground hover:underline ${FOCUS}`}
          >
            <Icon name="archive" size={16} />
            <span>{t("writing.shelf.empty.archiveDoor")}</span>
            <Icon name="arrowRight" size={14} />
          </button>
        )}
      </div>
    </section>
  );
}
