"use client";

/**
 * TagSuggestions — the suggestion listbox beneath TagInput (NOTES-001 §7).
 *
 * Presentational pill row wired as an ARIA listbox (repo convention:
 * MentionAutocomplete): each option carries aria-selected, while the parent
 * combobox input owns focus and points at the highlighted option via
 * aria-activedescendant. mousedown default is prevented so the input keeps
 * focus — its blur-add of the half-typed draft must not race this pick in
 * real browsers. Hover mirrors the keyboard highlight (single shared state).
 */

import { useTranslations } from "next-intl";

/**
 * DOM id of a listbox option. Shared with the parent combobox input's
 * aria-activedescendant so both sides stay in sync by construction.
 */
export function tagOptionId(listboxId: string, index: number): string {
  return `${listboxId}-option-${index}`;
}

export interface TagSuggestionsProps {
  readonly suggestions: readonly string[];
  readonly highlightedIndex: number;
  readonly listboxId: string;
  readonly onHighlight: (index: number) => void;
  readonly onPick: (tag: string) => void;
  /**
   * data-testid prefix for the option pills. Defaults to the editor's
   * "tag-suggestion"; consumers embedding the pills in another surface
   * (e.g. the filter bar) pass their own prefix to keep testids unique.
   */
  readonly testIdPrefix?: string;
}

export function TagSuggestions({
  suggestions,
  highlightedIndex,
  listboxId,
  onHighlight,
  onPick,
  testIdPrefix = "tag-suggestion",
}: TagSuggestionsProps) {
  const t = useTranslations("notes");

  return (
    <div
      id={listboxId}
      role="listbox"
      aria-label={t("editor.tagSuggestions")}
      className="flex flex-wrap gap-1"
    >
      {suggestions.map((tag, index) => {
        const isSelected = index === highlightedIndex;
        return (
          <button
            key={tag}
            type="button"
            role="option"
            aria-selected={isSelected}
            id={tagOptionId(listboxId, index)}
            data-testid={`${testIdPrefix}-${tag}`}
            onMouseDown={(event) => event.preventDefault()}
            onMouseEnter={() => onHighlight(index)}
            onClick={() => onPick(tag)}
            className={`cursor-pointer rounded-full border px-2 py-0.5 text-xs font-normal transition-colors duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
              isSelected
                ? "border-primary/30 bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:bg-accent hover:text-foreground"
            }`}
          >
            {tag}
          </button>
        );
      })}
    </div>
  );
}
