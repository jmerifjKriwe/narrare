"use client";

/**
 * NoteFilterBar — controlled filter bar for the scratchpad list (NOTES-001 §7).
 *
 * Owns no data fetching: the parent (ScratchpadWorkspace) owns filter state
 * and decides whether the list shows query results or semantic search
 * results. The semantic toggle is honest (RULE-11 spirit): the result badge
 * comes from the API response, not from this toggle.
 */

import { Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { NOTE_TYPE_KEYS, type NoteTypeKey } from "@/types";

export interface NoteFilters {
  q: string;
  note_type: NoteTypeKey | "";
  tag: string;
}

export interface NoteFilterBarProps {
  readonly filters: NoteFilters;
  readonly onFiltersChange: (filters: NoteFilters) => void;
  readonly availableTags: readonly string[];
  readonly semanticMode: boolean;
  readonly onSemanticModeChange: (enabled: boolean) => void;
  readonly onSearchSubmit: () => void;
}

export function NoteFilterBar({
  filters,
  onFiltersChange,
  availableTags,
  semanticMode,
  onSemanticModeChange,
  onSearchSubmit,
}: NoteFilterBarProps) {
  const t = useTranslations("notes");

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

      <label className="flex items-center gap-1.5 text-sm font-normal text-muted-foreground">
        <span className="sr-only sm:not-sr-only">{t("list.tagFilterLabel")}</span>
        <select
          value={filters.tag}
          data-testid="note-tag-filter"
          aria-label={t("list.tagFilterLabel")}
          className="cursor-pointer rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          onChange={(event) => onFiltersChange({ ...filters, tag: event.target.value })}
        >
          <option value="">{t("list.allTags")}</option>
          {availableTags.map((tag) => (
            <option key={tag} value={tag}>
              {tag}
            </option>
          ))}
        </select>
      </label>

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
