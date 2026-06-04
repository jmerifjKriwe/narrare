/**
 * useMentionAutocomplete — Custom hook for @mention autocomplete in KB textareas.
 *
 * Manages mention query extraction, autocomplete positioning,
 * keyboard navigation, and insertion logic.
 * Extracted from KBSectionEditor for RULE-04 compliance.
 */

import { useCallback, useEffect, useState } from "react";
import {
  calculateAutocompletePosition,
  extractMentionQuery,
  getInsertedMentionCursor,
  type MentionAutocompleteResult,
  replaceMentionAtCursor,
} from "./mentionAutocompleteUtils";

interface UseMentionAutocompleteOptions {
  value: string;
  name: string;
  onChange: (name: string, value: string) => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
}

export function useMentionAutocomplete({
  value,
  name,
  onChange,
  textareaRef,
}: UseMentionAutocompleteOptions) {
  const [mentionQuery, setMentionQuery] = useState("");
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [cursorPos, setCursorPos] = useState({ top: 0, left: 0 });
  const [selectedIndex, setSelectedIndex] = useState(0);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = e.target.value;
      const cursor = e.target.selectionStart;

      const query = extractMentionQuery(newValue, cursor);
      if (query) {
        setMentionQuery(query);
        setShowAutocomplete(true);
        setSelectedIndex(0);

        if (textareaRef.current) {
          const textareaWidth = textareaRef.current.getBoundingClientRect().width;
          setCursorPos(calculateAutocompletePosition(newValue, cursor, textareaWidth));
        }
      } else {
        setShowAutocomplete(false);
      }

      onChange(name, newValue);
    },
    [onChange, name, textareaRef],
  );

  /** Replace the @query text with @EntryName. */
  const insertMention = useCallback(
    (entryName: string) => {
      if (!textareaRef.current) return;
      const cursor = textareaRef.current.selectionStart;
      const text = value;
      const newValue = replaceMentionAtCursor(text, cursor, entryName);
      if (!newValue) return;

      onChange(name, newValue);
      setShowAutocomplete(false);

      requestAnimationFrame(() => {
        if (textareaRef.current) {
          const newCursor = getInsertedMentionCursor(text, cursor, entryName);
          if (newCursor === null) return;

          textareaRef.current.setSelectionRange(newCursor, newCursor);
          textareaRef.current.focus();
        }
      });
    },
    [value, onChange, name, textareaRef],
  );

  const handleKeyDown = useCallback(
    (autocompleteResults: MentionAutocompleteResult[] | undefined) =>
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
    [showAutocomplete, insertMention, selectedIndex],
  );

  // Close autocomplete on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (textareaRef.current && !textareaRef.current.contains(e.target as Node)) {
        setShowAutocomplete(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [textareaRef]);

  return {
    mentionQuery,
    showAutocomplete,
    cursorPos,
    selectedIndex,
    setSelectedIndex,
    handleChange,
    handleKeyDown: handleKeyDown,
    insertMention,
  };
}
