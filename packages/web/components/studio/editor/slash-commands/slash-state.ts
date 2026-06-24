/**
 * resolveSlashState (CR-AUFG-07-20).
 *
 * Pure-ish mapping from a TipTap editor's current state to the slash-menu state
 * (open/closed + query + slash position + caret-relative menu position + whether
 * a selection exists). Extracted from the React hook for testability and to keep
 * the hook under the RULE-04 hook line limit.
 *
 * This function performs no side effects and does not touch React state.
 */
import type { Editor } from "@tiptap/react";
import { parseSlashInput } from "./parser";

const CLOSED_POSITION = { top: 0, left: 0 };

export type ResolvedSlashState =
  | {
      readonly open: true;
      readonly query: string;
      /** Document offset of the `/` (used to delete it on select). */
      readonly slashPos: number;
      readonly position: { top: number; left: number };
      readonly hasSelection: boolean;
    }
  | { readonly open: false; readonly hasSelection: boolean };

/**
 * Inspect the editor and decide whether the slash menu should be open.
 *
 * Detection rules are delegated to {@link parseSlashInput}: the `/` must be the
 * first non-whitespace character of the current textblock (an "empty
 * paragraph"). A space or second slash after the query closes the menu so the
 * `/` remains as prose (spec §43).
 */
export function resolveSlashState(editor: Editor): ResolvedSlashState {
  if (editor.isDestroyed) return { open: false, hasSelection: false };

  const { from, to } = editor.state.selection;
  const hasSelection = from !== to;

  const $from = editor.state.selection.$from;
  const blockStart = $from.start();
  const textBefore = editor.state.doc.textBetween(blockStart, from, "");

  const parsed = parseSlashInput(textBefore, blockStart);
  if (!parsed) return { open: false, hasSelection };

  let position = CLOSED_POSITION;
  try {
    const rect = editor.view.coordsAtPos(parsed.slashPos);
    position = { top: rect.bottom, left: rect.left };
  } catch {
    position = CLOSED_POSITION;
  }

  return {
    open: true,
    query: parsed.query,
    slashPos: parsed.slashPos,
    position,
    hasSelection,
  };
}
