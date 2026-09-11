"use client";

/**
 * TagFilterCombobox — single-tag FILTER picker used by NoteFilterBar
 * (NOTES-001 §7: "tag filter (autocomplete chips)").
 *
 * Deliberately NOT the multi-chip editor (TagInput): this is a filter, so
 * exactly one tag can be active. While no tag is selected it renders a
 * combobox input whose typed prefix filters `availableTags` (suggestions
 * render via the shared TagSuggestions pill row, T22); while a tag is
 * selected the input is replaced by a single chip with a clear affordance.
 *
 * Because filtering by a nonexistent tag would be a dead end ("no notes
 * match"), Enter only commits an EXISTING tag — the keyboard-highlighted
 * suggestion, or the typed draft when it matches an available tag after
 * normalization (trim + lowercase, mirroring the backend rule). This is the
 * one intentional divergence from TagInput's free-form entry semantics.
 *
 * Keyboard/ARIA model follows the repo autocomplete convention
 * (TagInput / useMentionAutocomplete): ↑/↓ cycle the suggestions
 * (wrap-around), Enter picks, Escape clears the highlight; the input is
 * wired as a combobox (aria-expanded/-controls/-autocomplete/
 * -activedescendant) over a listbox of options.
 *
 * Controlled: `value` ("" = no tag filter) is the SSOT; selections and
 * clears are reported through `onChange` for the parent to echo back.
 */

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useMemo, useState } from "react";
import { TagSuggestions, tagOptionId } from "./TagSuggestions";

const MAX_SUGGESTIONS = 6;

export interface TagFilterComboboxProps {
  /** Active filter tag; "" means "no tag filter". */
  readonly value: string;
  readonly onChange: (tag: string) => void;
  /** All tags known to the parent (useNoteTags) — the only committable set. */
  readonly availableTags: readonly string[];
}

export function TagFilterCombobox({ value, onChange, availableTags }: TagFilterComboboxProps) {
  const t = useTranslations("notes");
  const [draft, setDraft] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const listboxId = useId();

  // Suggestions react to typing only (filter UX): an empty draft keeps the
  // popover closed — unlike TagInput, which doubles as an all-tags picker.
  const filteredSuggestions = useMemo(() => {
    const prefix = draft.trim().toLowerCase();
    if (!prefix) return [];
    return availableTags.filter((tag) => tag.startsWith(prefix)).slice(0, MAX_SUGGESTIONS);
  }, [draft, availableTags]);

  const showSuggestions = filteredSuggestions.length > 0;
  const highlighted = filteredSuggestions[highlightedIndex];

  function applyTag(tag: string) {
    onChange(tag);
    setDraft("");
    setHighlightedIndex(-1);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      if (highlighted) {
        applyTag(highlighted);
        return;
      }
      const typed = draft.trim().toLowerCase();
      if (typed && availableTags.includes(typed)) applyTag(typed);
      return;
    }
    if (event.key === "ArrowDown" && showSuggestions) {
      event.preventDefault();
      setHighlightedIndex((prev) => (prev + 1) % filteredSuggestions.length);
      return;
    }
    if (event.key === "ArrowUp" && showSuggestions) {
      event.preventDefault();
      // From "none highlighted" or the first option, wrap to the last.
      setHighlightedIndex((prev) => (prev <= 0 ? filteredSuggestions.length - 1 : prev - 1));
      return;
    }
    if (event.key === "Escape") {
      setHighlightedIndex(-1);
    }
  }

  // Selected state: one chip + clear affordance (TagInput chip language).
  if (value) {
    return (
      <span
        data-testid="note-filter-tag-chip"
        className="flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-xs font-normal text-foreground"
      >
        {value}
        <button
          type="button"
          data-testid="note-filter-tag-clear"
          aria-label={t("list.clearTagFilter")}
          className="cursor-pointer rounded-full p-0.5 text-muted-foreground transition-colors duration-100 hover:bg-foreground/10 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={() => onChange("")}
        >
          <X className="size-3" />
        </button>
      </span>
    );
  }

  return (
    <div className="relative">
      <input
        type="text"
        role="combobox"
        value={draft}
        data-testid="note-filter-tag-input"
        aria-label={t("list.tagFilterLabel")}
        placeholder={t("list.tagFilterPlaceholder")}
        aria-autocomplete="list"
        aria-expanded={showSuggestions}
        aria-controls={showSuggestions ? listboxId : undefined}
        aria-activedescendant={highlighted ? tagOptionId(listboxId, highlightedIndex) : undefined}
        className="w-44 rounded-md border border-border bg-background px-2.5 py-1.5 text-sm font-normal text-foreground transition-colors duration-150 placeholder:text-muted-foreground hover:border-muted-foreground/30 focus:outline-none focus:ring-2 focus:ring-ring"
        onChange={(event) => {
          setDraft(event.target.value);
          setHighlightedIndex(-1);
        }}
        onKeyDown={handleKeyDown}
      />
      {showSuggestions && (
        <div
          className="absolute left-0 top-full z-50 mt-1 w-max max-w-64 rounded-lg border border-border bg-popover p-2 shadow-lg"
          // Not a focus stop: TagSuggestions pills keep the combobox input's
          // focus (mousedown default prevented) per the shared convention.
        >
          <TagSuggestions
            suggestions={filteredSuggestions}
            highlightedIndex={highlightedIndex}
            listboxId={listboxId}
            onHighlight={setHighlightedIndex}
            onPick={applyTag}
            testIdPrefix="note-filter-tag-suggestion"
          />
        </div>
      )}
    </div>
  );
}
