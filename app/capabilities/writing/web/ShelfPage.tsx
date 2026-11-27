import { useCallback, useEffect, useId, useRef, useState, type MouseEvent, type ReactNode } from "react";

import { type Novel } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useActivityQuery, useNovelsQuery, takeNovelDeletedElsewhere } from "@shell/lib/query";
import { formatWordCount } from "@shell/lib/words";
import { Icon, type IconName } from "@shell/ui/icons";

import { pickHero, shelfGrid } from "./shelf";
import { filterGrid, genreFacets, hasActiveFilters, statusFacets } from "./shelfFilter";
import { NewBookDialog } from "./NewBookDialog";
import { ShelfBanner } from "./ShelfBanner";
import { BookCard } from "./ShelfBookCard";
import { ShelfEmpty } from "./ShelfEmpty";
import { ShelfHero } from "./ShelfHero";
import { ShelfSearch } from "./ShelfSearch";
import { ShelfSearchEmpty } from "./ShelfSearchEmpty";
import { ShelfError, ShelfLoading } from "./ShelfStates";

/**
 * The library shelf — the `shelf` draft family ported 1:1 onto the shell's
 * tokens (spec §6.2), the writing capability's `/` surface after the W3
 * handover. The hero is the latest-edited unarchived novel, the grid the
 * rest newest first; every figure is the row's own (word_count, target,
 * chapters, updated_at, status, series) — the drafts' populated states are
 * mock and never ship. A missing target keeps the landing's honest neutral
 * (the count alone, an empty track), a missing status no pill at all.
 *
 * The page rides inside the app-wide chrome (W4 Task 10, D15 / row 20):
 * the shell's rail and topbar frame the shelf — the brand, the breadcrumb,
 * the word total and the language switcher are the chrome's now, and the
 * landing's interim wordmark header retired with them. The language
 * contract is the shared shell home's (`@shell/lib/language`, D17 / #892):
 * the topbar chip is the post-setup switcher — the settings row is the
 * record, a choice applies at once and PATCHes the row, a refusal restores
 * the prior language. The pre-setup mirror stays setup's own seam; the
 * shelf is only ever reached once the row exists.
 *
 * The activity banner and the streak chip are real (Task 10): the atelier's
 * aggregate feeds the goal line (the hero book's own target), today's words,
 * the weekly average, the thirty-day sparkline and the streak; the write
 * family invalidates the activity key, so a chapter write moves the banner.
 * Doors the further build-out has not reached stay honestly disabled with
 * the drafted note, each comment naming its owning task: the banner's
 * statistics door (no statistics surface yet), import (the import wave). The
 * new-book door is real (Task 9): both copies open the drafted modal over
 * the scrimmed shelf, three fields and a live cover, one POST and the
 * shelf's own refetch. The search and filter chrome is real (Task 7):
 * client-side over the loaded list, the archive toggle a real refetch; the
 * per-book quick menu is real (Task 8): duplicate, export and archive with
 * the draft's confirm, busy and error states; the empty shelf's archive
 * door opens the archive-included list (Task 7's carried gap). The view
 * toggle stays inert — no task owns the list view yet. Loading, error and
 * empty answer per `shelf-states`
 * and `shelf-empty`; dark rides the tokens' light-dark pairs (`shelf-dark`
 * is the reference, not a second palette).
 *
 * Token mapping (the draft's hexes → the shell's roles): bg-canvas-light →
 * background (the body), surface-container-low → surface-container-low,
 * cover-sepia → primary for actions / cover-sepia for the bar fill,
 * text-muted-light/on-surface-variant → muted, state-warning → warning,
 * state-danger → danger, rule-light → rule. The Material concepts wear the
 * app's own icon faces (spec §6.9): library_books → books, file_upload →
 * uploadFile, format_ink_highlighter → inkHighlighter, schedule → clock,
 * cloud_off → warning (the set's established failure face), quill →
 * editNote, info → document.
 */

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control this page offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** One metric chip — the draft's quick-metrics geometry. */
function MetricChip({
  icon,
  iconClass,
  value,
  label,
}: {
  icon: IconName;
  iconClass: string;
  value: ReactNode;
  label: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-surface-container-low px-4 py-2.5 shadow-sm">
      <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${iconClass}`}>
        <Icon name={icon} size={18} />
      </div>
      <div>
        <div className="text-emph leading-none tabular-nums text-foreground">{value}</div>
        <div className="mt-0.5 text-eyebrow uppercase text-muted">{label}</div>
      </div>
    </div>
  );
}

export function ShelfPage() {
  const t = useTranslation();

  // Task 7's filter state — transient, the page's own memory: no URL, no
  // storage, a remount starts fresh (pinned). The archive toggle is the
  // list query's parameter, a real refetch; the rest narrows client-side
  // over the answer that query carried.
  const [query, setQuery] = useState("");
  const [genres, setGenres] = useState<readonly string[]>([]);
  const [statuses, setStatuses] = useState<readonly string[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);

  const novels = useNovelsQuery(includeArchived);
  // The atelier's activity aggregate — the streak chip's read; the banner
  // subscribes to the same key, so one ask serves both surfaces.
  const activity = useActivityQuery();
  const heroNoteId = useId();
  const doorsNoteId = useId();
  const bannerNoteId = useId();
  const emptyNoteId = useId();
  usePageTitle(t("writing.shelf.title"));

  // The workspace's 404 degrade (W4 Task 11): the book the workspace tried
  // to open was deleted elsewhere — the note seam's one-shot. Taken in an
  // EFFECT, never a render-phase initializer: a concurrent render may retry
  // the initializer and consume the one-shot without committing it.
  const [deletedElsewhere, setDeletedElsewhere] = useState(false);
  useEffect(() => {
    if (takeNovelDeletedElsewhere()) setDeletedElsewhere(true);
  }, []);

  // The new-book dialog (Task 9): transient page state — the dialog holds
  // its own answers and forgets them on unmount. The opener is remembered
  // so closing hands focus back to the very door that opened it; a create
  // from the empty panel retires that door with the panel, so the success
  // path lands on the top-bar door that survives the refetch instead.
  const [dialogOpen, setDialogOpen] = useState(false);
  const openerRef = useRef<HTMLButtonElement | null>(null);
  const topNewBookRef = useRef<HTMLButtonElement | null>(null);
  function openDialog(event: MouseEvent<HTMLButtonElement>) {
    openerRef.current = event.currentTarget;
    setDialogOpen(true);
  }
  const closeDialog = useCallback((created: boolean) => {
    setDialogOpen(false);
    const opener = openerRef.current;
    if (!created && opener !== null && opener.isConnected) opener.focus();
    else topNewBookRef.current?.focus();
  }, []);

  // The language switcher is the chrome's now (D17 / #892): the topbar chip
  // mounts the shared contract's post-setup face (`@shell/lib/language`) —
  // the row is the record, a refusal restores, no mirror write.

  // The retry keeps the error notice on screen with a busy button: a refetch
  // clears the query's error while it runs (the state goes pending again),
  // so the page's own flag holds the notice until the answer lands — the
  // draft's panel stays the context, never a flash of skeleton mid-retry.
  const [retrying, setRetrying] = useState(false);
  const lastError = useRef("");
  if (novels.error) {
    lastError.current = novels.error instanceof Error ? novels.error.message : String(novels.error);
  }
  function retry() {
    setRetrying(true);
    void novels.refetch().finally(() => setRetrying(false));
  }
  const showLoading = novels.isPending && !retrying;
  const showError = (novels.isError || retrying) && !novels.isSuccess;

  // The shelf's own seam: the novels query the capability's write paths
  // invalidate (the ["novels"] prefix, with the activity aggregate beside
  // it — one family, so a chapter write moves the banner too). Archived
  // books stay out by the API's default;
  // the archive toggle asks for them and the model guards the boundary
  // anyway. While the ask is in flight the skeleton stands (the toggle's
  // own refetch keeps the previous list — no skeleton flash); a failure is
  // the page's own notice with a working retry, never a dressed-up shelf;
  // an empty list is the honest empty state.
  const rows: readonly Novel[] = novels.data ?? [];
  const hero = pickHero(rows);
  const filterState = { query, genres, statuses };
  const gridAll = shelfGrid(rows, hero, includeArchived);
  const grid = filterGrid(gridAll, filterState);
  const narrowing = hasActiveFilters(filterState);
  // The facets answer the whole loaded population — the hero included,
  // the archive too when the toggle asked for it. The grid never doubles
  // the hero (the shelf's fixed lead), so a facet may count a book the
  // grid itself does not show.
  const genreOptions = genreFacets(rows);
  const statusOptions = statusFacets(rows);
  const active = rows.filter((novel) => novel.archived_at == null);
  const totalWords = active.reduce((sum, novel) => sum + novel.word_count, 0);

  function toggleGenre(label: string) {
    setGenres((previous) =>
      previous.includes(label) ? previous.filter((entry) => entry !== label) : [...previous, label],
    );
  }
  function toggleStatus(value: string) {
    setStatuses((previous) =>
      previous.includes(value) ? previous.filter((entry) => entry !== value) : [...previous, value],
    );
  }
  /** The popover's reset clears its own controls — the facets and the
   *  archive toggle. The search box is its own control and keeps its text. */
  function resetFilters() {
    setGenres([]);
    setStatuses([]);
    setIncludeArchived(false);
  }
  /** The empty-search panel's door: everything back to the whole shelf. */
  function clearSearchAndFilters() {
    setQuery("");
    resetFilters();
  }
  const pendingValue = <span aria-hidden="true" className="block h-4 w-16 animate-pulse rounded bg-soft" />;
  const booksValue = novels.isPending
    ? pendingValue
    : novels.isSuccess
      ? t("writing.shelf.metrics.books", { count: active.length })
      : "—";
  const wordsValue = novels.isPending ? pendingValue : novels.isSuccess ? formatWordCount(totalWords) : "—";
  // The streak is the aggregate's own day count — an honest 0 when none,
  // a placeholder while the ask runs, the family's dash on a failure.
  const streakValue = activity.isPending
    ? pendingValue
    : activity.isSuccess
      ? t("writing.shelf.metrics.streak", { count: activity.data.streak_days })
      : "—";

  return (
    // The draft's body: full-bleed parchment inside the chrome's scrolling
    // main. The shell owns the one <main> landmark and the rail/topbar
    // frame (W4 Task 10); this is its content — the wordmark header the
    // landing interim carried retired with the chrome's arrival (row 20).
    <div className="flex min-h-full w-full flex-col selection:bg-secondary-container selection:text-secondary-container-foreground">
      <div className="mx-auto w-full max-w-7xl flex-1 space-y-8 px-4 py-8 lg:px-8">
        {/* The title bar and the quick-metrics strip. */}
        <div className="flex flex-col justify-between gap-4 pb-1 lg:flex-row lg:items-end">
          <div>
            <div className="mb-1.5 flex items-center gap-2">
              <span className="text-eyebrow uppercase tracking-widest text-area-writing">
                {t("writing.shelf.eyebrow")}
              </span>
            </div>
            <h1 className={`${SERIF} text-3xl font-semibold tracking-tight text-primary`}>
              {t("writing.shelf.title")}
            </h1>
            <p className="mt-1 text-body text-muted">{t("writing.shelf.subtitle")}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <MetricChip
              icon="books"
              iconClass="bg-surface-container-high text-primary"
              value={booksValue}
              label={t("writing.shelf.metrics.booksLabel")}
            />
            <MetricChip
              icon="historyEdu"
              iconClass="bg-secondary-container text-primary"
              value={wordsValue}
              label={t("writing.shelf.metrics.wordsLabel")}
            />
            {/* The streak chip — Task 10 wired it to the activity
                aggregate; the flame is the draft's own mark. */}
            <MetricChip
              icon="localFire"
              iconClass="bg-surface-container-high text-warning"
              value={streakValue}
              label={t("writing.shelf.metrics.streakLabel")}
            />
            {/* The primary actions — the new-book door opens Task 9's
                dialog; the import door stays disabled, its future-facing
                note shared with the adjacent live new-book CTA. */}
            <div className="flex flex-col items-start gap-1 pl-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled
                  aria-describedby={doorsNoteId}
                  className="flex h-9 cursor-not-allowed items-center gap-1.5 rounded-lg border border-border bg-surface-container px-3 text-label text-foreground opacity-50 shadow-sm"
                >
                  <Icon name="uploadFile" size={17} />
                  <span>{t("writing.shelf.import")}</span>
                </button>
                <button
                  type="button"
                  ref={topNewBookRef}
                  onClick={openDialog}
                  className={`flex h-9 items-center gap-1.5 rounded-lg bg-primary px-3.5 text-label font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-95 ${FOCUS}`}
                >
                  <Icon name="plus" size={17} />
                  <span>{t("writing.shelf.newBook")}</span>
                </button>
              </div>
              <p id={doorsNoteId} className="text-meta text-muted">
                {t("writing.shelf.comingSoon")}
              </p>
            </div>
          </div>
        </div>

        {/* The deleted-elsewhere note — the workspace's 404 degrade, once. */}
        {deletedElsewhere && (
          <p role="status" className="rounded-lg border border-border bg-surface-container-low px-4 py-3 text-body text-muted">
            {t("writing.shelf.deletedElsewhere")}
          </p>
        )}

        {/* The content, by the list's own state. Nothing to show — no
            active hero and no grid rows (the archive included only when
            the toggle asked) — is the drafted empty panel, no chrome.
            With books, the hero leads when an active one exists (the
            archive-only shelf answers with the grid alone), and the grid
            under the chrome is the filtered rest — or the honest
            empty-search panel when a real narrowing answers nothing. */}
        {showLoading ? (
          <ShelfLoading />
        ) : showError ? (
          <ShelfError message={lastError.current} retrying={retrying} onRetry={retry} />
        ) : hero === null && gridAll.length === 0 ? (
          <ShelfEmpty
            noteId={emptyNoteId}
            archiveIncluded={includeArchived}
            onBrowseArchive={() => setIncludeArchived(true)}
            onNewBook={openDialog}
          />
        ) : (
          <>
            {hero !== null && <ShelfHero novel={hero} noteId={heroNoteId} />}
            <div className="space-y-6">
              <ShelfSearch
                query={query}
                onQueryChange={setQuery}
                genres={genres}
                statuses={statuses}
                includeArchived={includeArchived}
                genreFacets={genreOptions}
                statusFacets={statusOptions}
                resultCount={grid.length}
                onToggleGenre={toggleGenre}
                onToggleStatus={toggleStatus}
                onToggleArchived={() => setIncludeArchived((previous) => !previous)}
                onResetFilters={resetFilters}
              />
              {narrowing && grid.length === 0 ? (
                <ShelfSearchEmpty onClear={clearSearchAndFilters} />
              ) : (
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
                  {grid.map((novel) => (
                    <BookCard key={novel.id} novel={novel} />
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {/* The activity banner — Task 10's surface, live on the aggregate;
            the goal line reads the atelier's daily goal (W4 row 25). */}
        <ShelfBanner noteId={bannerNoteId} />
      </div>

      {/* The new-book dialog — mounted only while open, so its answers are
          transient by construction; the scrim covers the shelf above. */}
      {dialogOpen && <NewBookDialog onClose={closeDialog} />}
    </div>
  );
}
