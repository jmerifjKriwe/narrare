/**
 * Selection-context extraction shared by the AI selection tools.
 *
 * The backend caps `context_before` / `context_after` at 500 chars for both
 * rewrite (`apps/api/narrare/writing/schemas_rewrite.py`) and co-author
 * (`apps/api/narrare/writing/schemas_coauthor.py`). Extracting with a radius
 * of exactly that cap guarantees compliant payloads by construction (audit
 * B01: a local radius of 800 produced a guaranteed 422 on nearly every
 * selection).
 */

import type { Editor } from "@tiptap/react";

/** Maximum characters of before/after context the backend accepts. */
export const AI_CONTEXT_RADIUS_CHARS = 500;

/** Context around a selection, capped to the backend limit. */
export interface SelectionContext {
  contextBefore: string;
  contextAfter: string;
}

/** Extract up to {@link AI_CONTEXT_RADIUS_CHARS} of context around a range. */
export function getSelectionContext(editor: Editor, from: number, to: number): SelectionContext {
  return {
    contextBefore: editor.state.doc.textBetween(
      Math.max(0, from - AI_CONTEXT_RADIUS_CHARS),
      from,
      " ",
    ),
    contextAfter: editor.state.doc.textBetween(
      to,
      Math.min(editor.state.doc.content.size, to + AI_CONTEXT_RADIUS_CHARS),
      " ",
    ),
  };
}
