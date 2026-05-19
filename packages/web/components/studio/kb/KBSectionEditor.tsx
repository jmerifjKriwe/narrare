"use client";

/**
 * Guided section textarea for KB template sections with @mention autocomplete.
 *
 * When the user types "@" followed by 2+ characters, queries the KB
 * autocomplete endpoint and shows a floating dropdown.  Selecting an
 * entry inserts @EntryName into the text.
 */

import { BookOpen, FileText, type LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";
import { useKBAutocomplete } from "@/lib/hooks/useKB";

/** Map known icon names to lucide components. */
const ICON_MAP: Record<string, LucideIcon> = {
  BookOpen,
  Eye: BookOpen, // fallback — we keep BookOpen for sections
  Heart: BookOpen,
  FileText,
};

interface KBSectionEditorProps {
  /** Section name (used as heading). */
  name: string;
  /** Lucide icon name for the section header. */
  icon: string;
  /** Tailwind color class for the icon (e.g., "text-amber-500"). */
  iconColor: string;
  /** Localized section title. */
  title: string;
  /** Hint text shown below the title. */
  hint: string;
  /** Current textarea value. */
  value: string;
  /** Called with the new value on change. */
  onChange: (name: string, value: string) => void;
  /** Error message if any. */
  error?: string;
  /** Novel ID for @mention autocomplete (optional — disables autocomplete if omitted). */
  novelId?: string;
}

export function KBSectionEditor({
  name,
  icon,
  iconColor,
  title,
  hint,
  value,
  onChange,
  error,
  novelId,
}: KBSectionEditorProps) {
  const t = useTranslations("studio");
  const IconComponent = ICON_MAP[icon] ?? FileText;
  const wordCount = value ? value.trim().split(/\s+/).filter(Boolean).length : 0;
  const charCount = value.length;
  const fieldId = `kb-section-${name}`;
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // @mention autocomplete state
  const [mentionQuery, setMentionQuery] = useState("");
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [cursorPos, setCursorPos] = useState({ top: 0, left: 0 });
  const [selectedIndex, setSelectedIndex] = useState(0);

  const { data: autocompleteResults, isFetching: autocompleteLoading } = useKBAutocomplete(
    novelId ?? "",
    mentionQuery,
  );

  /** Extract @mention query from cursor position. */
  const extractMentionQuery = useCallback((text: string, cursor: number): string | null => {
    const beforeCursor = text.slice(0, cursor);
    const atIndex = beforeCursor.lastIndexOf("@");
    if (atIndex === -1) return null;

    // Check there's no word character right before @ (must be a boundary)
    if (atIndex > 0 && /\w/.test(beforeCursor[atIndex - 1])) return null;

    const afterAt = beforeCursor.slice(atIndex + 1);
    // Only match if it starts with a letter
    if (!afterAt || !/^[A-Za-zÀ-ÖØ-öø-ÿ]/.test(afterAt)) return null;

    // Extract continuous word chars (letters, spaces, hyphens, apostrophes)
    const match = afterAt.match(/^[A-Za-zÀ-ÖØ-öø-ÿ\s'-]+/);
    if (!match) return null;

    const query = match[0];
    // Only trigger autocomplete for 2+ characters
    if (query.length < 2) return null;

    return query;
  }, []);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = e.target.value;
      const cursor = e.target.selectionStart;

      // Extract @mention query
      const query = extractMentionQuery(newValue, cursor);
      if (query) {
        setMentionQuery(query);
        setShowAutocomplete(true);
        setSelectedIndex(0);

        // Position the dropdown near the cursor
        if (textareaRef.current) {
          const rect = textareaRef.current.getBoundingClientRect();
          // Approximate position based on line height
          const textBefore = newValue.slice(0, cursor);
          const lines = textBefore.split("\n");
          const lineHeight = 22; // approximate px per line
          const charWidth = 8.5; // approximate px per character
          const currentLine = lines.length - 1;
          const currentCol = lines[currentLine]?.length ?? 0;

          setCursorPos({
            top: currentLine * lineHeight + lineHeight + 6,
            left: Math.min(currentCol * charWidth, rect.width - 280),
          });
        }
      } else {
        setShowAutocomplete(false);
      }

      onChange(name, newValue);
    },
    [onChange, name, extractMentionQuery],
  );

  /** Replace the @query text with @EntryName. */
  const insertMention = useCallback(
    (entryName: string) => {
      if (!textareaRef.current) return;
      const cursor = textareaRef.current.selectionStart;
      const text = value;
      const beforeCursor = text.slice(0, cursor);
      const atIndex = beforeCursor.lastIndexOf("@");
      if (atIndex === -1) return;

      const afterAt = beforeCursor.slice(atIndex + 1);
      const match = afterAt.match(/^[A-Za-zÀ-ÖØ-öø-ÿ\s'-]+/);
      if (!match) return;

      const afterMention = text.slice(atIndex + 1 + match[0].length);
      const newValue = `${text.slice(0, atIndex)}@${entryName}${afterMention}`;

      onChange(name, newValue);
      setShowAutocomplete(false);

      requestAnimationFrame(() => {
        if (textareaRef.current) {
          const newCursor = atIndex + 1 + entryName.length;
          textareaRef.current.setSelectionRange(newCursor, newCursor);
          textareaRef.current.focus();
        }
      });
    },
    [value, onChange, name],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (!showAutocomplete || !autocompleteResults?.length) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % autocompleteResults.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex(
          (prev) => (prev - 1 + autocompleteResults.length) % autocompleteResults.length,
        );
      } else if (e.key === "Enter" || e.key === "Tab") {
        const selected = autocompleteResults[selectedIndex];
        if (selected) {
          e.preventDefault();
          insertMention(selected.name);
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        setShowAutocomplete(false);
      }
    },
    [showAutocomplete, autocompleteResults, selectedIndex, insertMention],
  );

  // Close autocomplete on blur
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (textareaRef.current && !textareaRef.current.contains(e.target as Node)) {
        setShowAutocomplete(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="border border-border/60 rounded-lg bg-card shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3.5 bg-gradient-to-b from-muted/20 to-transparent">
        <div className={`shrink-0 ${iconColor}`}>
          <IconComponent className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          <p className="text-xs text-muted-foreground/60 mt-0.5">{hint}</p>
        </div>
      </div>

      {/* Textarea */}
      <div className="px-4 pb-3 relative">
        <textarea
          ref={textareaRef}
          id={fieldId}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={hint}
          rows={5}
          className={`
            w-full px-3 py-2.5 rounded-md text-sm resize-y min-h-[100px]
            bg-gradient-to-b from-input-background via-input-background to-muted/20
            border border-border/50
            transition-all duration-150
            placeholder:text-muted-foreground/40 placeholder:italic
            focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/10
            ${error ? "border-destructive focus:border-destructive focus:ring-destructive/20" : ""}
          `}
          aria-invalid={!!error}
          aria-describedby={error ? `${fieldId}-error` : undefined}
          aria-autocomplete="list"
          aria-controls={showAutocomplete ? `${fieldId}-autocomplete` : undefined}
          aria-activedescendant={
            showAutocomplete && autocompleteResults?.[selectedIndex]
              ? `${fieldId}-option-${selectedIndex}`
              : undefined
          }
        />
        {error && (
          <p id={`${fieldId}-error`} className="text-xs text-destructive mt-1" role="alert">
            {error}
          </p>
        )}

        {/* @mention autocomplete dropdown */}
        {showAutocomplete && novelId && (
          <div
            id={`${fieldId}-autocomplete`}
            role="listbox"
            className="absolute z-50 left-3 right-3 bg-popover border border-border rounded-lg shadow-lg
              max-h-[200px] overflow-y-auto"
            style={{
              top: cursorPos.top + 30, // below the textarea
            }}
          >
            {autocompleteLoading && (
              <div className="px-3 py-2 text-xs text-muted-foreground/60">{t("kb.searching")}</div>
            )}
            {!autocompleteLoading &&
              autocompleteResults &&
              autocompleteResults.length > 0 &&
              autocompleteResults.map((entry, idx) => (
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
                    insertMention(entry.name);
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                >
                  <span className="text-muted-foreground/60 text-xs font-mono">@</span>
                  <span className="font-medium">{entry.name}</span>
                  <span className="ml-auto text-[11px] text-muted-foreground/50 capitalize">
                    {entry.entity_type}
                  </span>
                </button>
              ))}
            {!autocompleteLoading && autocompleteResults && autocompleteResults.length === 0 && (
              <div className="px-3 py-2 text-xs text-muted-foreground/50">
                {t("kb.noMatchingEntries")}
              </div>
            )}
          </div>
        )}

        {/* Word/char count */}
        <div className="flex justify-end gap-3 mt-1.5">
          <span className="text-[11px] text-muted-foreground/40 tabular-nums">
            {wordCount} {wordCount === 1 ? "word" : "words"}
          </span>
          <span className="text-[11px] text-muted-foreground/40 tabular-nums">
            {charCount} {charCount === 1 ? "char" : "chars"}
          </span>
        </div>
      </div>
    </div>
  );
}
