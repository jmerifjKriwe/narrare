"use client";

/**
 * NoteFilterBar — controlled filter bar for the scratchpad list (NOTES-001 §7).
 *
 * Owns no data fetching: the parent (ScratchpadWorkspace) owns filter state
 * and decides whether the list shows query results or semantic search
 * results. The semantic toggle is honest (RULE-11 spirit): the result badge
 * comes from the API response, not from this toggle.
 *
 * Composition (RULE-04): each filter control is its own module —
 * - TagFilterCombobox: single-tag autocomplete filter (§7 "autocomplete
 *   chips"), NOT the multi-chip editor; commit semantics documented there.
 * - NoteScopeSelect: the grouped novel/series select (§7 "only if linked
 *   notes exist"). The bar owns only the WHEN: it mounts the select while
 *   `hasLinks` is true AND at least one of `novels`/`series` is non-empty —
 *   `hasLinks` is the parent's "at least one loaded note is linked" signal
 *   (spec gate), the list check keeps the select from degrading to a lone
 *   "All" option. All filter changes flow through the single
 *   `onFiltersChange(NoteFilters)` callback (scope as a typed object).
 */

import { Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { NOTE_TYPE_KEYS, type NoteTypeKey } from "@/types";
import { type NoteScopeFilter, NoteScopeSelect, type ScopeOption } from "./NoteScopeSelect";
import { TagFilterCombobox } from "./TagFilterCombobox";

// Contract re-exports: consumers (T26 ScratchpadWorkspace, tests) import the
// filter contract from the bar; the scope sub-types live canonically in
// NoteScopeSelect.
export type { NoteScopeFilter, ScopeOption } from "./NoteScopeSelect";

export interface NoteFilters {
  q: string;
  note_type: NoteTypeKey | "";
  tag: string;
  scope: NoteScopeFilter | null;
}

export interface NoteFilterBarProps {
  readonly filters: NoteFilters;
  readonly onFiltersChange: (filters: NoteFilters) => void;
  readonly availableTags: readonly string[];
  readonly novels: readonly ScopeOption[];
  readonly series: readonly ScopeOption[];
  /** True when at least one loaded note is linked — gates the scope select. */
  readonly hasLinks: boolean;
  readonly semanticMode: boolean;
  readonly onSemanticModeChange: (enabled: boolean) => void;
  readonly onSearchSubmit: () => void;
}

export function NoteFilterBar({
  filters,
  onFiltersChange,
  availableTags,
  novels,
  series,
  hasLinks,
  semanticMode,
  onSemanticModeChange,
  onSearchSubmit,
}: NoteFilterBarProps) {
  const t = useTranslations("notes");

  const showScope = hasLinks && (novels.length > 0 || series.length > 0);

  return (
    <div
      data-testid="note-filter-bar"
      className="flex flex-wrap items-center gap-2 border-b border-border p-3"
    >
      <div className="relative min-w-48 flex-1">
        <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          value={filters.q}
          aria-label={t("list.searchPlaceholder")}
          placeholder={t("list.searchPlaceholder")}
          data-testid="note-search-input"
          className="w-full rounded-md border border-border bg-background py-1.5 pl-8 pr-3 text-sm font-normal placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          onChange={(event) => onFiltersChange({ ...filters, q: event.target.value })}
          onKeyDown={(event) => {
            if (event.key === "Enter") onSearchSubmit();
          }}
        />
      </div>

      <label className="flex items-center gap-1.5 text-sm font-normal text-muted-foreground">
        <span className="sr-only sm:not-sr-only">{t("list.typeFilterLabel")}</span>
        <select
          value={filters.note_type}
          data-testid="note-type-filter"
          aria-label={t("list.typeFilterLabel")}
          className="cursor-pointer rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          onChange={(event) =>
            onFiltersChange({
              ...filters,
              note_type: event.target.value as NoteTypeKey | "",
            })
          }
        >
          <option value="">{t("list.allTypes")}</option>
          {NOTE_TYPE_KEYS.map((key) => (
            <option key={key} value={key}>
              {t(`type.${key}`)}
            </option>
          ))}
        </select>
      </label>

      <TagFilterCombobox
        value={filters.tag}
        onChange={(tag) => onFiltersChange({ ...filters, tag })}
        availableTags={availableTags}
      />

      {showScope && (
        <NoteScopeSelect
          value={filters.scope}
          onChange={(scope) => onFiltersChange({ ...filters, scope })}
          novels={novels}
          series={series}
        />
      )}

      <label className="flex cursor-pointer items-center gap-1.5 text-sm font-normal text-muted-foreground">
        <input
          type="checkbox"
          checked={semanticMode}
          data-testid="note-semantic-toggle"
          className="size-4 cursor-pointer accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
          onChange={(event) => onSemanticModeChange(event.target.checked)}
        />
        {t("search.semanticToggle")}
      </label>
    </div>
  );
}
