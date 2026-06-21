/**
 * ghost-text-error-status — Transient fetch-error decoration helpers.
 *
 * Extracted from ghost-text-helpers.ts to comply with RULE-04 file-size
 * limits (modularize, don't compress). These functions manage the
 * low-noise, non-blocking error affordance for GhostText fetch failures
 * (CR-AUFG-07-15).
 *
 * Design constraints:
 * - AbortError is always silent (normal typing cancellation).
 * - Non-AbortError shows a transient localized decoration that auto-clears.
 * - All visible text comes from extension options (injected by React) —
 *   no hardcoded English in this non-React module (ADR-043 Note 7).
 */

import type { Editor } from "@tiptap/core";
import type { GhostTextOptions, GhostTextStorage } from "./ghost-text-types";

/**
 * Clears any transient fetch-error decoration (CR-AUFG-07-15).
 *
 * Cancels the auto-clear timer and resets `_errorStatusVisible`. Dispatches an
 * empty transaction so the decoration plugin re-renders (removes the error
 * span from the DOM). Safe to call when no error is visible (no-op).
 *
 * @param editor Optional — dispatches a transaction to trigger re-render.
 *               Omitted in cleanup() where the editor is already destroyed.
 */
export function clearErrorStatus(storage: GhostTextStorage, editor?: Editor): void {
  if (storage._errorTimer) {
    clearTimeout(storage._errorTimer);
    storage._errorTimer = null;
  }
  if (storage._errorStatusVisible) {
    storage._errorStatusVisible = false;
    if (editor && !editor.isDestroyed) {
      editor.view.dispatch(editor.state.tr);
    }
  }
}

/**
 * Shows a transient, non-blocking fetch-error decoration (CR-AUFG-07-15).
 *
 * Sets `_errorStatusVisible = true`, anchors the decoration at the current
 * cursor position (`suggestionPos`), and schedules an auto-clear after
 * `options.errorStatusDurationMs` ms. The visible text comes from
 * `options.errorStatusText` (injected by React, never hardcoded English).
 *
 * Called only for non-AbortError rejections — normal typing cancellation
 * (AbortError) stays completely silent.
 *
 * @param options Extension options carrying localized text + duration.
 */
export function showErrorStatus(
  storage: GhostTextStorage,
  editor: Editor,
  options: GhostTextOptions,
): void {
  clearErrorStatus(storage, editor);

  storage._errorStatusVisible = true;
  storage.suggestionPos = editor.state.selection.head;

  if (!editor.isDestroyed) {
    editor.view.dispatch(editor.state.tr);
  }

  const duration = options.errorStatusDurationMs ?? 4000;
  storage._errorTimer = setTimeout(() => {
    storage._errorStatusVisible = false;
    storage._errorTimer = null;
    if (!editor.isDestroyed) {
      editor.view.dispatch(editor.state.tr);
    }
  }, duration);
}
