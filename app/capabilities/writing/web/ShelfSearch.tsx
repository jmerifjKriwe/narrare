/**
 * The shelf's search and filter chrome — the `shelf` draft's bar and the
 * `shelf-filter-open` draft's popover, ported onto the shell's tokens.
 * Task 7 makes them real: the search answers titles, genre components and
 * figures (the disclosed equality shape, shelfFilter.ts), the popover
 * facets the loaded rows' own genres and statuses, and „Archiv
 * einbeziehen" drives the list query's `include_archived` — a real
 * refetch, never a client hide.
 *
 * The popover is the draft's geometry exactly: the w-64 panel under the
 * trigger, the „Filtern" header with its close, the facet rows (checkbox,
 * label, count), the footer's „Zurücksetzen" beside the selection count,
 * and the trigger's secondary-container face with the sepia dot while a
 * filter stands. The status section and the archive switch are undrafted
 * — they wear the genre section's own facet language (the draft's footer
 * rule between sections), no invented layout. Changes apply live; the
 * draft draws no apply button, so there is none.
 *
 * Semantics: a non-modal dialog (`role="dialog"`, labelled, the trigger
 * `aria-haspopup`/`aria-expanded`/`aria-controls`), Escape closes and
 * returns focus to the trigger, the close button likewise, a click
 * outside closes without stealing focus, and opening moves focus to the
 * close button — the states-reference discipline. The facet rows are real
 * checkboxes (sr-only inputs under the drafted boxes), the archive row a
 * real switch. Below the draft's own breakpoint the panel anchors right
 * so it never leaves the viewport; from `sm` up it keeps the draft's
 * left anchor. The view toggle stays Task 6's honest inert pair — no task
 * owns the list view yet.
 */

import { useEffect, useId, useRef, useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import type { GenreFacet, StatusFacet } from "./shelfFilter";
import { STATUS_PILL } from "./ShelfBookCard";

/** The shell's focus ring on every control this chrome offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** One facet row — the draft's label geometry over a real checkbox: the
 *  input is sr-only, the drafted box wears its state and the focus ring,
 *  the count stands right. Checked rows carry the medium label weight the
 *  draft draws; the box fills with the sepia and the check. */
function FacetRow({
  label,
  count,
  checked,
  onToggle,
}: {
  label: string;
  count: number;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <label className="group flex cursor-pointer items-center justify-between rounded-lg px-1.5 py-1.5 transition-colors hover:bg-surface-container">
      <span className="flex items-center gap-2.5">
        <input
          type="checkbox"
          className="peer sr-only"
          checked={checked}
          onChange={onToggle}
          aria-label={label}
        />
        <span
          aria-hidden="true"
          className={
            checked
              ? `flex h-4 w-4 shrink-0 items-center justify-center rounded bg-cover-sepia text-cover-sepia-ink peer-focus-visible:outline-hidden peer-focus-visible:ring-2 peer-focus-visible:ring-focus`
              : `h-4 w-4 shrink-0 rounded border border-outline-variant bg-surface group-hover:border-outline peer-focus-visible:outline-hidden peer-focus-visible:ring-2 peer-focus-visible:ring-focus`
          }
        >
          {checked && <Icon name="check" size={14} />}
        </span>
        <span className={`text-label text-foreground ${checked ? "font-medium" : ""}`}>{label}</span>
      </span>
      <span className="text-meta tabular-nums text-muted">{count}</span>
    </label>
  );
}

/** The facet section's eyebrow — the draft's 10px tracked label. The draft
 *  draws it in the outline ink, which fails the WCAG AA contrast floor at
 *  this size in both token halves (the live axe run's finding); the muted
 *  ink — the header eyebrow's own — keeps the geometry and passes. */
function FacetHeading({ children }: { children: string }) {
  return (
    <div className="px-1.5 pb-1">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-muted">{children}</span>
    </div>
  );
}

export type ShelfSearchProps = {
  query: string;
  onQueryChange: (query: string) => void;
  genres: readonly string[];
  statuses: readonly string[];
  includeArchived: boolean;
  genreFacets: readonly GenreFacet[];
  statusFacets: readonly StatusFacet[];
  /** The grid's current answer, announced politely to the reader. */
  resultCount: number;
  onToggleGenre: (label: string) => void;
  onToggleStatus: (value: string) => void;
  onToggleArchived: () => void;
  onResetFilters: () => void;
};

export function ShelfSearch({
  query,
  onQueryChange,
  genres,
  statuses,
  includeArchived,
  genreFacets,
  statusFacets,
  resultCount,
  onToggleGenre,
  onToggleStatus,
  onToggleArchived,
  onResetFilters,
}: ShelfSearchProps) {
  const t = useTranslation();
  const [open, setOpen] = useState(false);
  const popoverId = useId();
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);

  // The archive toggle counts with the facets: it narrows the population
  // the same way, and the dot/count answer every standing filter.
  const selectedCount = genres.length + statuses.length + (includeArchived ? 1 : 0);
  const active = open || selectedCount > 0;

  /** Close; `returnFocus` is the Escape/close-button path — an outside
   *  click leaves the focus where the reader put it. */
  function close(returnFocus: boolean) {
    setOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  }

  // While the popover stands: Escape closes and returns focus, a press
  // outside closes without stealing it. Both listeners leave when it
  // closes — nothing outlives the panel.
  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    }
    function onDown(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open]);

  // Opening moves the focus to the panel's first control — the header's
  // close, the draft's own order.
  useEffect(() => {
    if (open) closeRef.current?.focus();
  }, [open]);

  return (
    <div className="flex flex-col items-center justify-between gap-3 pb-1 sm:flex-row">
      <div className="flex w-full items-center gap-2 sm:w-auto">
        {/* The search box — the draft's geometry, live. Escape clears the
            query, the keyboard path back to the whole shelf. */}
        <div className="flex h-9 w-full items-center gap-2 rounded-lg border border-border bg-surface px-3 shadow-sm sm:w-72">
          <span className="text-muted">
            <Icon name="search" size={18} />
          </span>
          <input
            type="text"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape" && query !== "") {
                event.preventDefault();
                onQueryChange("");
              }
            }}
            placeholder={t("writing.shelf.search.placeholder")}
            aria-label={t("writing.shelf.search.placeholder")}
            className="w-full bg-transparent text-label text-foreground placeholder:text-muted focus:outline-none"
          />
        </div>
        {/* The filter trigger and its popover — the draft's wrapper. */}
        <div ref={wrapperRef} className="relative z-50 shrink-0">
          <button
            type="button"
            ref={triggerRef}
            aria-haspopup="dialog"
            aria-expanded={open}
            aria-controls={popoverId}
            onClick={() => (open ? close(false) : setOpen(true))}
            className={
              active
                ? `flex h-9 shrink-0 items-center gap-1.5 rounded-lg border border-outline-variant bg-secondary-container px-3 text-label font-semibold text-primary shadow-sm transition-colors ${FOCUS}`
                : `flex h-9 shrink-0 items-center gap-1.5 rounded-lg border border-border bg-surface px-3 text-label text-muted shadow-sm transition-colors hover:text-foreground ${FOCUS}`
            }
          >
            <Icon name="tune" size={18} />
            <span>{t("writing.shelf.search.filter")}</span>
            {selectedCount > 0 && (
              <span aria-hidden="true" className="ml-0.5 h-1.5 w-1.5 rounded-full bg-primary" />
            )}
          </button>
          {open && (
            <div
              id={popoverId}
              role="dialog"
              aria-label={t("writing.shelf.filter.title")}
              className="absolute right-0 top-full z-50 mt-2 w-64 select-none rounded-xl border border-outline-variant bg-surface-container-lowest p-2 shadow-lg sm:left-0 sm:right-auto"
            >
              {/* The header — „Filtern" and the close, the draft's rule under. */}
              <div className="flex items-center justify-between border-b border-rule px-1.5 pb-2">
                <span className="text-eyebrow font-semibold uppercase tracking-wider text-muted">
                  {t("writing.shelf.filter.title")}
                </span>
                <button
                  type="button"
                  ref={closeRef}
                  aria-label={t("writing.shelf.filter.close")}
                  onClick={() => close(true)}
                  className={`rounded p-0.5 text-muted transition-colors hover:text-foreground ${FOCUS}`}
                >
                  <Icon name="cross" size={16} />
                </button>
              </div>
              {/* Genre — the drafted facet section, the rows' real values. */}
              <div className="pb-1 pt-2">
                <FacetHeading>{t("writing.shelf.filter.genre")}</FacetHeading>
                <div className="space-y-0.5">
                  {genreFacets.map((facet) => (
                    <FacetRow
                      key={facet.label}
                      label={facet.label}
                      count={facet.count}
                      checked={genres.includes(facet.label)}
                      onToggle={() => onToggleGenre(facet.label)}
                    />
                  ))}
                </div>
              </div>
              {/* Status — undrafted, the genre section's own language, the
                  draft's footer rule between the sections. */}
              {statusFacets.length > 0 && (
                <div className="mt-1 border-t border-rule pb-1 pt-2">
                  <FacetHeading>{t("writing.shelf.filter.status")}</FacetHeading>
                  <div className="space-y-0.5">
                    {statusFacets.map((facet) => {
                      const pill = STATUS_PILL[facet.value];
                      if (pill === undefined) return null;
                      return (
                        <FacetRow
                          key={facet.value}
                          label={t(pill.key)}
                          count={facet.count}
                          checked={statuses.includes(facet.value)}
                          onToggle={() => onToggleStatus(facet.value)}
                        />
                      );
                    })}
                  </div>
                </div>
              )}
              {/* The archive switch — undrafted, the facet row's geometry
                  with a switch in the count's place. A real refetch knob:
                  the page answers it with the list query's parameter. */}
              <div className="mt-1 border-t border-rule pb-1 pt-2">
                <button
                  type="button"
                  role="switch"
                  aria-checked={includeArchived}
                  onClick={onToggleArchived}
                  className={`flex w-full cursor-pointer items-center justify-between rounded-lg px-1.5 py-1.5 transition-colors hover:bg-surface-container ${FOCUS}`}
                >
                  <span className={`text-label text-foreground ${includeArchived ? "font-medium" : ""}`}>
                    {t("writing.shelf.filter.archive")}
                  </span>
                  <span
                    aria-hidden="true"
                    className={`relative h-4 w-7 shrink-0 rounded-full transition-colors ${
                      includeArchived ? "bg-cover-sepia" : "bg-surface-container-highest"
                    }`}
                  >
                    <span
                      className={`absolute left-0.5 top-0.5 h-3 w-3 rounded-full bg-cover-sepia-ink transition-transform ${
                        includeArchived ? "translate-x-3" : ""
                      }`}
                    />
                  </span>
                </button>
              </div>
              {/* The footer — reset beside the selection count, live. The
                  draft's sepia link is the primary token's light half
                  exactly; the dark half needs the action ink to stay
                  readable (the live axe run's second finding). */}
              <div className="mt-1 flex items-center justify-between border-t border-rule px-1.5 pt-2">
                <button
                  type="button"
                  onClick={onResetFilters}
                  className={`cursor-pointer text-meta text-primary transition-colors hover:text-foreground hover:underline ${FOCUS}`}
                >
                  {t("writing.shelf.filter.reset")}
                </button>
                <span className="text-eyebrow text-muted">
                  {t("writing.shelf.filter.selected", { count: selectedCount })}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
      {/* The view toggle — no task owns the list view yet; the pair stays
          honestly inert, Task 6's faces unchanged. */}
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
      {/* The grid's answer, announced politely — the reader hears the
          narrowing without watching the grid. */}
      <p role="status" className="sr-only">
        {t("writing.shelf.search.results", { count: resultCount })}
      </p>
    </div>
  );
}
