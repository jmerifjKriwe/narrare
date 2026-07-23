"use client";

import type { Editor } from "@tiptap/react";
import { useEffect, useState } from "react";

/**
 * Reads the editor's current text selection and keeps it live.
 *
 * Reuses the WRITE-004 rewrite accessor
 * (`editor.state.doc.textBetween(selection.from, selection.to, " ")`) so the
 * Dialogue Coach panel sees the exact same "selection" notion as the rewrite
 * flow. Returns `null` when there is no editor or the selection is collapsed
 * (empty) — the panel disables its run actions on a null selection.
 *
 * The subscription mirrors {@link useAnnotationMarkTracker} /
 * {@link useGhostTextOnboardingAnchor}: `transaction` covers every selection
 * change (caret moves, mouse drags, typing). The hook is consumed inside the
 * scoped `DialogueCoachPanelSlot`, so only that side panel re-renders on a
 * selection change — the editor canvas is left untouched (vercel-react-best-
 * practices: localise re-render scope).
 *
 * @module useEditorSelectionText
 */

function readSelection(editor: Editor | null): string | null {
  if (!editor) return null;
  const { from, to, empty } = editor.state.selection;
  if (empty) return null;
  const text = editor.state.doc.textBetween(from, to, " ").trim();
  return text.length > 0 ? text : null;
}

export function useEditorSelectionText(editor: Editor | null): string | null {
  const [selectionText, setSelectionText] = useState<string | null>(() => readSelection(editor));

  useEffect(() => {
    // Sync immediately so a freshly-arriving editor (or its initial selection)
    // is reflected without waiting for the first transaction.
    setSelectionText(readSelection(editor));
    if (!editor) return;

    const update = () => setSelectionText(readSelection(editor));
    editor.on("transaction", update);
    return () => {
      editor.off("transaction", update);
    };
  }, [editor]);

  return selectionText;
}
