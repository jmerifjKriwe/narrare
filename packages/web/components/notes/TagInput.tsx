"use client";

/**
 * TagInput — chips + free-form text entry with prefix autocomplete
 * (NOTES-001 §7: "tag autocomplete over existing tags; new tags always
 * allowed"). Normalization mirrors the backend rule (trim, lowercase,
 * collapse whitespace) and the 32-char tag length (core NoteLimits parity);
 * duplicates and the 10-tag cap are ignored silently at entry — the API
 * would reject them anyway, and quick entry stays fast.
 *
 * Keyboard model follows the repo autocomplete convention
 * (useMentionAutocomplete): ↑/↓ cycle the suggestions (wrap-around), Enter
 * picks the highlighted option — or adds the typed draft when nothing is
 * highlighted — and Escape clears the highlight. The input is wired as a
 * combobox (aria-expanded/-controls/-autocomplete/-activedescendant) over a
 * listbox of options. Backspace on an empty draft removes the last chip
 * (KBTagInput convention).
 *
 * Tags are semi-controlled: `value` is the source of truth, mirrored into
 * state during render when the parent passes a new array (React's
 * "adjusting state when a prop changes" pattern). This keeps the
 * duplicate/cap checks correct even when a parent does not immediately
 * echo `onChange` back into `value`.
 */

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useMemo, useRef, useState } from "react";
import { TagSuggestions, tagOptionId } from "./TagSuggestions";

const MAX_TAG_LENGTH = 32;
const MAX_SUGGESTIONS = 6;

function normalizeTag(tag: string): string {
  return tag.trim().replace(/\s+/g, " ").toLowerCase();
}

export interface TagInputProps {
  readonly value: readonly string[];
  readonly onChange: (next: string[]) => void;
  readonly suggestions: readonly string[];
  readonly placeholder?: string;
  readonly maxTags?: number;
}

export function TagInput({
  value,
  onChange,
  suggestions,
  placeholder,
  maxTags = 10,
}: TagInputProps) {
  const t = useTranslations("notes");
  const [draft, setDraft] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const listboxId = useId();

  // Semi-controlled mirror of the parent's value (see component docs).
  const [tags, setTags] = useState<readonly string[]>(value);
  const valueRef = useRef(value);
  if (value !== valueRef.current) {
    valueRef.current = value;
    setTags(value);
  }

  const filteredSuggestions = useMemo(() => {
    const prefix = draft.trim().toLowerCase();
    return suggestions
      .filter((tag) => !tags.includes(tag))
      .filter((tag) => (prefix ? tag.startsWith(prefix) : true))
      .slice(0, MAX_SUGGESTIONS);
  }, [draft, suggestions, tags]);

  const showSuggestions = filteredSuggestions.length > 0;
  const highlighted = filteredSuggestions[highlightedIndex];

  function addTag(raw: string) {
    const tag = normalizeTag(raw).slice(0, MAX_TAG_LENGTH);
    if (!tag || tags.includes(tag) || tags.length >= maxTags) return;
    const next = [...tags, tag];
    setTags(next);
    onChange(next);
    setDraft("");
    setHighlightedIndex(-1);
  }

  function removeTag(tag: string) {
    const next = tags.filter((existing) => existing !== tag);
    setTags(next);
    onChange(next);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      // A keyboard-highlighted suggestion wins; otherwise the draft is a
      // free-form new tag (spec §7: new tags always allowed).
      addTag(highlighted ?? draft);
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
      return;
    }
    if (event.key === "Backspace" && draft === "" && tags.length > 0) {
      removeTag(tags[tags.length - 1] as string);
    }
  }

  return (
    <div className="space-y-1.5">
      {/* Unified field container (KBTagInput visual convention): chips and a
          borderless input read as ONE form field; focus-within rings it. */}
      <div
        data-testid="tag-chips"
        className="flex min-h-[38px] w-full cursor-text flex-wrap items-center gap-1.5 rounded-md border border-border bg-background px-2 py-1.5 transition-colors duration-150 hover:border-muted-foreground/30 focus-within:border-muted-foreground/30 focus-within:ring-2 focus-within:ring-ring"
      >
        {tags.map((tag) => (
          <span
            key={tag}
            className="flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-normal"
          >
            {tag}
            <button
              type="button"
              data-testid={`tag-remove-${tag}`}
              aria-label={`${t("editor.delete")} ${tag}`}
              className="cursor-pointer rounded-full p-0.5 text-muted-foreground transition-colors duration-100 hover:bg-foreground/10 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={() => removeTag(tag)}
            >
              <X className="size-3" />
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          value={draft}
          data-testid="tag-input"
          aria-label={t("editor.tagPlaceholder")}
          placeholder={placeholder ?? t("editor.tagPlaceholder")}
          aria-autocomplete="list"
          aria-expanded={showSuggestions}
          aria-controls={showSuggestions ? listboxId : undefined}
          aria-activedescendant={highlighted ? tagOptionId(listboxId, highlightedIndex) : undefined}
          className="min-w-32 flex-1 border-none bg-transparent px-1 py-0.5 text-sm outline-none placeholder:text-muted-foreground"
          onChange={(event) => {
            setDraft(event.target.value);
            setHighlightedIndex(-1);
          }}
          onKeyDown={handleKeyDown}
          onBlur={() => draft && addTag(draft)}
        />
      </div>
      {showSuggestions && (
        <TagSuggestions
          suggestions={filteredSuggestions}
          highlightedIndex={highlightedIndex}
          listboxId={listboxId}
          onHighlight={setHighlightedIndex}
          onPick={addTag}
        />
      )}
    </div>
  );
}
