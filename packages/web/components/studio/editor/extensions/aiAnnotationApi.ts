/**
 * AIAnnotation public API — standalone functions for mark lifecycle operations.
 *
 * These functions take the TipTap `editor` as an explicit parameter, bypassing
 * TipTap's Proxy-based `this` context. React components should import and call
 * these directly with their `editor` prop.
 *
 * Used by: ContinueButton, AIAnnotationActions, Autosave, commands
 */

import type { Editor } from "@tiptap/core";
import type { EditorState } from "@tiptap/pm/state";

// ── Types ──────────────────────────────────────────────────────────────────

export interface AIAnnotationAttrs {
  requestId: string;
  source: "extend" | "rewrite" | "unblock";
  originalText: string;
  status: "pending" | "resolved";
  createdAt: string;
}

export interface PendingModification {
  original: string;
  current: string;
  requestId: string;
}

export interface FeedbackCallbacks {
  onAccept: (requestId: string, source: string, originalText: string) => void;
  onReject: (requestId: string, source: string, originalText: string) => void;
  onModify: (requestId: string, source: string, originalText: string, modifiedText: string) => void;
}

// ── Internal helper ────────────────────────────────────────────────────────

function findPendingMarks(
  state: EditorState,
): { from: number; to: number; attrs: AIAnnotationAttrs }[] {
  const results: { from: number; to: number; attrs: AIAnnotationAttrs }[] = [];
  const markType = state.schema.marks.aiGenerated;
  if (!markType) return results;

  state.doc.descendants((node, pos) => {
    if (!node.isText) return;
    const mark = node.marks.find((m) => m.type === markType && m.attrs.status === "pending");
    if (mark) {
      results.push({
        from: pos,
        to: pos + node.nodeSize,
        attrs: mark.attrs as unknown as AIAnnotationAttrs,
      });
    }
  });
  return results;
}

// ── Public API ─────────────────────────────────────────────────────────────

/** Resolve all pending marks: remove marks (keep text), trigger feedback. */
export function resolveAllPendingMarks(editor: Editor, callbacks: FeedbackCallbacks | null): void {
  const markType = editor.state.schema.marks.aiGenerated;
  if (!markType) return;

  const pending = findPendingMarks(editor.state);
  if (pending.length === 0) return;

  const { tr } = editor.state;
  for (const { from, to, attrs } of pending) {
    const currentText = editor.state.doc.textBetween(from, to);
    const originalText = attrs.originalText || "";
    tr.removeMark(from, to, markType);

    if (callbacks) {
      if (originalText && currentText !== originalText) {
        callbacks.onModify(attrs.requestId, attrs.source, originalText, currentText);
      } else {
        callbacks.onAccept(attrs.requestId, attrs.source, originalText);
      }
    }
  }
  editor.view.dispatch(tr);
}

/** Insert AI content at the current cursor position with a pending mark. */
export function insertAIContent(
  editor: Editor,
  callbacks: FeedbackCallbacks | null,
  text: string,
  requestId: string,
  source: string,
): void {
  if (editor.isDestroyed) return;

  // Single-pending-mark constraint: resolve any existing pending mark first
  resolveAllPendingMarks(editor, callbacks);

  const attrs: AIAnnotationAttrs = {
    requestId,
    source: source as AIAnnotationAttrs["source"],
    originalText: text,
    status: "pending",
    createdAt: new Date().toISOString(),
  };

  const markType = editor.state.schema.marks.aiGenerated;
  if (!markType) return;

  const mark = markType.create(attrs);
  const pos = editor.state.selection.from;
  const { tr } = editor.state;
  tr.insertText(text, pos);
  tr.addMark(pos, pos + text.length, mark);
  editor.view.dispatch(tr);
  editor.commands.setTextSelection(pos + text.length);
}

/** Append streaming text to the end of the pending mark range. */
export function appendToPendingMark(editor: Editor, text: string): string {
  if (editor.isDestroyed) return text;

  const pending = findPendingMarks(editor.state);
  if (pending.length === 0) return text;

  const last = pending[pending.length - 1];
  const markType = editor.state.schema.marks.aiGenerated;
  if (!markType) return text;

  const existingMark = editor.state.doc
    .resolve(last.from)
    .marks()
    .find((m) => m.type === markType && m.attrs.status === "pending");
  if (!existingMark) return text;

  const { tr } = editor.state;
  tr.insertText(text, last.to);
  tr.addMark(last.from, last.to + text.length, existingMark);
  editor.view.dispatch(tr);

  return text;
}

/** Finalize the pending mark: update originalText with accumulated text. */
export function finalizePendingMark(editor: Editor, accumulatedOriginal: string): void {
  if (editor.isDestroyed) return;

  const pending = findPendingMarks(editor.state);
  if (pending.length === 0) return;

  const markType = editor.state.schema.marks.aiGenerated;
  if (!markType) return;

  const { from, to } = pending[0];
  const existingMark = editor.state.doc
    .resolve(from)
    .marks()
    .find((m) => m.type === markType && m.attrs.status === "pending");
  if (!existingMark) return;

  const updatedMark = markType.create({
    ...existingMark.attrs,
    originalText: accumulatedOriginal,
  });

  const { tr } = editor.state;
  tr.removeMark(from, to, markType);
  tr.addMark(from, to, updatedMark);
  editor.view.dispatch(tr);
}

/** Accept a pending mark: remove the mark (keep text), trigger feedback. */
export function acceptMark(
  editor: Editor,
  callbacks: FeedbackCallbacks | null,
  requestId: string,
): void {
  if (editor.isDestroyed) return;
  const markType = editor.state.schema.marks.aiGenerated;
  if (!markType) return;

  const pending = findPendingMarks(editor.state);
  const mark = pending.find((m) => m.attrs.requestId === requestId);
  if (!mark) return;

  const currentText = editor.state.doc.textBetween(mark.from, mark.to);
  const originalText = mark.attrs.originalText || "";

  const { tr } = editor.state;
  tr.removeMark(mark.from, mark.to, markType);
  editor.view.dispatch(tr);

  if (callbacks) {
    if (originalText && currentText !== originalText) {
      callbacks.onModify(requestId, mark.attrs.source, originalText, currentText);
    } else {
      callbacks.onAccept(requestId, mark.attrs.source, originalText);
    }
  }
}

/** Reject a pending mark: delete the marked text, trigger feedback. */
export function rejectMark(
  editor: Editor,
  callbacks: FeedbackCallbacks | null,
  requestId: string,
): void {
  if (editor.isDestroyed) return;
  const markType = editor.state.schema.marks.aiGenerated;
  if (!markType) return;

  const pending = findPendingMarks(editor.state);
  const mark = pending.find((m) => m.attrs.requestId === requestId);
  if (!mark) return;

  const originalText = mark.attrs.originalText || "";

  const { tr } = editor.state;
  tr.delete(mark.from, mark.to);
  editor.view.dispatch(tr);

  if (callbacks) {
    callbacks.onReject(requestId, mark.attrs.source, originalText);
  }
}

/** Check if there is a pending AI annotation mark. */
export function hasPendingMark(editor: Editor): boolean {
  if (editor.isDestroyed) return false;
  return findPendingMarks(editor.state).length > 0;
}

/** Get pending modification info by comparing original text with current text. */
export function getPendingModification(editor: Editor): PendingModification | null {
  if (editor.isDestroyed) return null;
  const pending = findPendingMarks(editor.state);
  if (pending.length === 0) return null;

  const { from, to, attrs } = pending[0];
  const currentText = editor.state.doc.textBetween(from, to);
  const originalText = attrs.originalText || "";

  if (originalText && currentText !== originalText) {
    return {
      original: originalText,
      current: currentText,
      requestId: attrs.requestId,
    };
  }
  return null;
}
