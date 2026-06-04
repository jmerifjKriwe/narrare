"use client";

/**
 * Guided section textarea for KB template sections with @mention autocomplete.
 *
 * When the user types "@" followed by 2+ characters, queries the KB
 * autocomplete endpoint and shows a floating dropdown.  Selecting an
 * entry inserts @EntryName into the text.
 */

import { BookOpen, FileText, type LucideIcon } from "lucide-react";
import { useRef } from "react";
import { useKBAutocomplete } from "@/lib/hooks/useKB";
import { MentionAutocomplete } from "./MentionAutocomplete";
import { useMentionAutocomplete } from "./useMentionAutocomplete";

/** Map known icon names to lucide components. */
const ICON_MAP: Record<string, LucideIcon> = {
  BookOpen,
  Eye: BookOpen,
  Heart: BookOpen,
  FileText,
};

interface KBSectionEditorProps {
  name: string;
  icon: string;
  iconColor: string;
  title: string;
  hint: string;
  value: string;
  onChange: (name: string, value: string) => void;
  error?: string;
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
  const IconComponent = ICON_MAP[icon] ?? FileText;
  const wordCount = value ? value.trim().split(/\s+/).filter(Boolean).length : 0;
  const charCount = value.length;
  const fieldId = `kb-section-${name}`;
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const {
    mentionQuery,
    showAutocomplete,
    cursorPos,
    selectedIndex,
    setSelectedIndex,
    handleChange,
    handleKeyDown,
    insertMention,
  } = useMentionAutocomplete({
    value,
    name,
    onChange,
    textareaRef,
  });

  const { data: autocompleteResults, isFetching: autocompleteLoading } = useKBAutocomplete(
    novelId ?? "",
    mentionQuery,
  );

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
          onKeyDown={handleKeyDown(autocompleteResults)}
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
          <MentionAutocomplete
            fieldId={fieldId}
            cursorPos={cursorPos}
            results={autocompleteResults}
            isLoading={autocompleteLoading}
            selectedIndex={selectedIndex}
            onSelect={insertMention}
            onHover={setSelectedIndex}
          />
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
