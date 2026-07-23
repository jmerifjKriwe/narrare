"use client";

import type { Editor } from "@tiptap/react";
import { DialogueCoachPanel } from "../analysis/DialogueCoachPanel";
import { useEditorSelectionText } from "../editor/useEditorSelectionText";

interface DialogueCoachPanelSlotProps {
  editor: Editor | null;
  chapterId: string;
  onClose: () => void;
}

/**
 * Owns the editor-selection subscription for the Dialogue Coach panel.
 *
 * Extracted from {@link EditorPanelContent} for two reasons:
 *
 * 1. **Re-render scope** — {@link useEditorSelectionText} re-renders on every
 *    editor transaction (caret moves, mouse drags, typing). Housing it here
 *    means only this side panel re-renders when the writer changes the
 *    selection; the metadata / readability / etc. panels and the editor canvas
 *    are left untouched (vercel-react-best-practices: localise state).
 * 2. **RULE-04** — keeps {@link EditorPanelContent} under the 200-line cap
 *    without compressing its exhaustive panel switch.
 *
 * The {@link DialogueCoachPanel} itself stays a pure consumer of
 * `selectionText` (Task 8 contract); this slot is the wiring layer that turns
 * the live editor selection into that prop.
 */
export function DialogueCoachPanelSlot({
  editor,
  chapterId,
  onClose,
}: DialogueCoachPanelSlotProps) {
  const selectionText = useEditorSelectionText(editor);
  if (!editor) return null;
  return (
    <DialogueCoachPanel
      chapterId={chapterId}
      selectionText={selectionText}
      editor={editor}
      onClose={onClose}
    />
  );
}
