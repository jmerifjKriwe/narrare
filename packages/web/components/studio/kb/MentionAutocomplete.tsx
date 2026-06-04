"use client";

/**
 * MentionAutocomplete — Floating dropdown for @mention autocomplete in KB sections.
 *
 * Extracted from KBSectionEditor for RULE-04 compliance.
 */

import { useTranslations } from "next-intl";

/** Matches the return shape of useKBAutocomplete items. */
interface AutocompleteEntry {
  id: string;
  name: string;
  entity_type: string;
  slug: string;
}

interface MentionAutocompleteProps {
  fieldId: string;
  cursorPos: { top: number; left: number };
  results: AutocompleteEntry[] | undefined;
  isLoading: boolean;
  selectedIndex: number;
  onSelect: (entryName: string) => void;
  onHover: (index: number) => void;
}

export function MentionAutocomplete({
  fieldId,
  cursorPos,
  results,
  isLoading,
  selectedIndex,
  onSelect,
  onHover,
}: MentionAutocompleteProps) {
  const t = useTranslations("studio");

  return (
    <div
      id={`${fieldId}-autocomplete`}
      role="listbox"
      className="absolute z-50 left-3 right-3 bg-popover border border-border rounded-lg shadow-lg
        max-h-[200px] overflow-y-auto"
      style={{
        top: cursorPos.top + 30,
      }}
    >
      {isLoading && (
        <div className="px-3 py-2 text-xs text-muted-foreground/60">{t("kb.searching")}</div>
      )}
      {!isLoading &&
        results &&
        results.length > 0 &&
        results.map((entry, idx) => (
          <button
            key={entry.id}
            type="button"
            id={`${fieldId}-option-${idx}`}
            role="option"
            aria-selected={idx === selectedIndex}
            className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2
              transition-colors duration-100
              ${
                idx === selectedIndex
                  ? "bg-primary/10 text-primary"
                  : "text-foreground hover:bg-muted/50"
              }`}
            onMouseDown={(e) => {
              e.preventDefault();
              onSelect(entry.name);
            }}
            onMouseEnter={() => onHover(idx)}
          >
            <span className="text-muted-foreground/60 text-xs font-mono">@</span>
            <span className="font-medium">{entry.name}</span>
            <span className="ml-auto text-[11px] text-muted-foreground/50 capitalize">
              {entry.entity_type}
            </span>
          </button>
        ))}
      {!isLoading && results && results.length === 0 && (
        <div className="px-3 py-2 text-xs text-muted-foreground/50">
          {t("kb.noMatchingEntries")}
        </div>
      )}
    </div>
  );
}
