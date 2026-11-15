import { Fragment, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { client, type Novel } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { useTranslation } from "@shell/lib/i18n";
import { activeLocale, applyLocale, chosenLocale, type Locale } from "@shell/lib/locale";
import { usePageTitle } from "@shell/lib/pageTitle";
import { queryClient, useNovelsQuery } from "@shell/lib/query";
import { formatWordCount } from "@shell/lib/words";
import { Icon, type IconName } from "@shell/ui/icons";

import { pickHero, shelfGrid } from "./shelf";
import { ShelfBanner } from "./ShelfBanner";
import { BookCard } from "./ShelfBookCard";
import { ShelfEmpty } from "./ShelfEmpty";
import { ShelfHero } from "./ShelfHero";
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
 * The page carries its own wordmark header, the landing's established
 * post-setup pattern: the draft's rail and editor top bar are shell chrome
 * that returns with the shell rebuild, and a document breadcrumb or a
 * „Saved" pill on the shelf would claim a state no row backs. The language
 * switcher is the post-setup contract — the settings row is the record, a
 * choice applies at once and PATCHes the row, a refusal restores the prior
 * language. The pre-setup mirror stays setup's own seam; the shelf is only
 * ever reached once the row exists.
 *
 * Doors the further build-out has not reached stay honestly disabled with
 * the drafted note, each comment naming its owning task: the new-book
 * dialog (Task 9), the search/filter chrome (Task 7), the per-book quick
 * menu (Task 8), the activity banner and the streak chip (Task 10), import
 * (the import wave). Loading, error and empty answer per `shelf-states`
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

/** The draft draws DE|EN|FR with DE leading; the switcher keeps that order. */
const SWITCHER_ORDER: readonly Locale[] = ["de", "en", "fr"];

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

/** The search/filter/view chrome — Task 7's surface, honestly inert until
 *  then: the drafted geometry, disabled controls, no invented results. */
function SearchChrome() {
  const t = useTranslation();
  return (
    <div className="flex flex-col items-center justify-between gap-3 pb-1 sm:flex-row">
      <div className="flex w-full items-center gap-2 sm:w-auto">
        <div className="flex h-9 w-full items-center gap-2 rounded-lg border border-border bg-surface px-3 shadow-sm sm:w-72">
          <span className="text-muted">
            <Icon name="search" size={18} />
          </span>
          <input
            type="text"
            disabled
            placeholder={t("writing.shelf.search.placeholder")}
            aria-label={t("writing.shelf.search.placeholder")}
            className="w-full cursor-not-allowed bg-transparent text-label text-foreground opacity-50 placeholder:text-muted focus:outline-none"
          />
        </div>
        <button
          type="button"
          disabled
          className="flex h-9 shrink-0 cursor-not-allowed items-center gap-1.5 rounded-lg border border-border bg-surface px-3 text-label text-foreground opacity-50 shadow-sm"
        >
          <Icon name="tune" size={18} />
          <span>{t("writing.shelf.search.filter")}</span>
        </button>
      </div>
      <div className="flex items-center gap-2 self-end sm:self-auto">
        <span className="text-meta text-muted">{t("writing.shelf.search.view")}</span>
        <button
          type="button"
          disabled
          aria-pressed="true"
          aria-label={t("writing.shelf.search.viewGrid")}
          className="cursor-not-allowed rounded-lg bg-surface-container-high p-1.5 text-primary opacity-50 shadow-sm"
        >
          <Icon name="gridView" size={18} />
        </button>
        <button
          type="button"
          disabled
          aria-pressed="false"
          aria-label={t("writing.shelf.search.viewList")}
          className="cursor-not-allowed rounded-lg p-1.5 text-muted opacity-50"
        >
          <Icon name="viewList" size={18} />
        </button>
      </div>
    </div>
  );
}

export function ShelfPage() {
  // useTranslation subscribes to the locale store, so reading activeLocale
  // in render stays fresh across a switch — the landing's same subscription.
  const t = useTranslation();
  const locale = activeLocale();
  const novels = useNovelsQuery();
  const heroNoteId = useId();
  const doorsNoteId = useId();
  const menuNoteId = useId();
  const bannerNoteId = useId();
  const emptyNoteId = useId();
  const radioRefs = useRef<Partial<Record<Locale, HTMLButtonElement | null>>>({});
  usePageTitle(t("writing.shelf.title"));

  /** Apply a locale and write the row — the post-setup contract. The row
   *  exists once setup has run: a success invalidates the cached row so the
   *  shell adopts the written choice; a refusal restores the prior language.
   *  No mirror write — the pre-setup mirror is setup's seam, spent by then. */
  async function choose(next: Locale) {
    if (next === activeLocale()) return;
    const previous = chosenLocale();
    applyLocale(next);
    try {
      const { response } = await client.PATCH("/api/settings", { body: { locale: next } });
      if (!response.ok) throw new Error(`refused: ${response.status}`);
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    } catch {
      applyLocale(previous);
    }
  }

  /** The radio group's keyboard contract, the landing's: arrows cycle and
   *  wrap, Home/End jump to the ends; the move selects and focuses, and the
   *  roving tabindex keeps the group one tab stop. */
  function radioKey(event: KeyboardEvent<HTMLButtonElement>, at: number) {
    const span = SWITCHER_ORDER.length;
    let next: number;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (at + 1) % span;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (at - 1 + span) % span;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = span - 1;
    else return;
    event.preventDefault();
    const code = SWITCHER_ORDER[next];
    void choose(code);
    radioRefs.current[code]?.focus();
  }

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
  // invalidate (["novels"]). Archived books stay out by the API's default;
  // the model guards the boundary anyway. While the ask is in flight the
  // skeleton stands; a failure is the page's own notice with a working
  // retry, never a dressed-up shelf; an empty list is the honest empty state.
  const rows: readonly Novel[] = novels.data ?? [];
  const hero = pickHero(rows);
  const grid = shelfGrid(rows, hero);
  const active = rows.filter((novel) => novel.archived_at == null);
  const totalWords = active.reduce((sum, novel) => sum + novel.word_count, 0);
  const pendingValue = <span aria-hidden="true" className="block h-4 w-16 animate-pulse rounded bg-soft" />;
  const booksValue = novels.isPending
    ? pendingValue
    : novels.isSuccess
      ? t("writing.shelf.metrics.books", { count: active.length })
      : "—";
  const wordsValue = novels.isPending ? pendingValue : novels.isSuccess ? formatWordCount(totalWords) : "—";

  return (
    // The draft's body: full-bleed parchment, the header sticky above it.
    // The shell owns the one <main> landmark; this is its content.
    <div className="flex min-h-screen w-full flex-col selection:bg-secondary-container selection:text-secondary-container-foreground">
      {/* The wordmark header — the landing's established post-setup chrome. */}
      <header className="sticky top-0 z-40 w-full border-b border-border bg-panel">
        <div className="mx-auto flex min-h-14 w-full max-w-7xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-2 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-7 w-7 items-center justify-center rounded border border-outline-variant bg-cover-ink shadow-sm">
              <span className={`${SERIF} text-title font-semibold leading-none text-surface-container-lowest`}>
                N
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className={`${SERIF} text-title font-semibold tracking-tight text-primary`}>
                {t("writing.shelf.wordmark")}
              </span>
              <span aria-hidden="true" className="text-meta text-muted">
                /
              </span>
              <span className="text-label font-medium text-muted">{t("writing.shelf.breadcrumb")}</span>
            </div>
          </div>
          <div
            role="radiogroup"
            aria-label={t("writing.shelf.language")}
            className="flex items-center rounded border border-border bg-surface-container-low px-1 py-0.5 text-meta"
          >
            {SWITCHER_ORDER.map((code, at) => (
              <Fragment key={code}>
                {at > 0 && (
                  <span aria-hidden="true" className="px-0.5 text-border">
                    |
                  </span>
                )}
                <button
                  type="button"
                  role="radio"
                  aria-label={catalogs[code]["locale.name"]}
                  aria-checked={code === locale}
                  tabIndex={code === locale ? 0 : -1}
                  ref={(node) => {
                    radioRefs.current[code] = node;
                  }}
                  onKeyDown={(event) => radioKey(event, at)}
                  onClick={() => void choose(code)}
                  className={
                    code === locale
                      ? `rounded bg-surface-container-lowest px-1.5 py-0.5 font-semibold text-primary shadow-sm ${FOCUS}`
                      : `rounded px-1.5 py-0.5 text-muted transition-colors hover:text-foreground ${FOCUS}`
                  }
                >
                  {code.toUpperCase()}
                </button>
              </Fragment>
            ))}
          </div>
        </div>
      </header>

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
            {/* Task 10 wires the streak from the activity aggregate; until
                then the chip stands neutral, never an invented day count. */}
            <MetricChip
              icon="localFire"
              iconClass="bg-surface-container-high text-warning"
              value="—"
              label={t("writing.shelf.metrics.streakLabel")}
            />
            {/* The primary actions — Task 9 wires the new-book dialog; the
                import wave opens the import door. Both honest until then,
                the drafted note standing right under them. */}
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
                  disabled
                  aria-describedby={doorsNoteId}
                  className="flex h-9 cursor-not-allowed items-center gap-1.5 rounded-lg bg-primary px-3.5 text-label font-semibold text-primary-foreground opacity-50 shadow-sm"
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

        {/* The content, by the list's own state. */}
        {showLoading ? (
          <ShelfLoading />
        ) : showError ? (
          <ShelfError message={lastError.current} retrying={retrying} onRetry={retry} />
        ) : hero === null ? (
          <ShelfEmpty noteId={emptyNoteId} />
        ) : (
          <>
            <ShelfHero novel={hero} noteId={heroNoteId} />
            <div className="space-y-6">
              <SearchChrome />
              <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
                {grid.map((novel) => (
                  <BookCard key={novel.id} novel={novel} menuNoteId={menuNoteId} />
                ))}
              </div>
              {/* The quick menus' shared note — Task 8's door, once per card. */}
              <p id={menuNoteId} className="text-meta text-muted">
                {t("writing.shelf.comingSoon")}
              </p>
            </div>
          </>
        )}

        {/* The activity banner — Task 10's surface, neutral until then. */}
        <ShelfBanner noteId={bannerNoteId} />
      </div>
    </div>
  );
}
