/**
 * ghost-text-helpers — Internal helper functions for the GhostText extension.
 *
 * All functions operate on explicit (storage, editor, options) parameters
 * instead of closures, avoiding TypeScript issues with Extension.create()'s
 * Proxy-based `this` context.
 *
 * Extracted from GhostText.ts to keep the extension definition under the
 * 400-line file-size limit (RULE-04: modularize, don't compress).
 */

import type { Editor } from "@tiptap/core";
import type { Transaction } from "@tiptap/pm/state";
import { ReplaceStep } from "@tiptap/pm/transform";
import { simulateSuggestion } from "./ghost-text-suggestions";
import type { GhostTextOptions, GhostTextStorage } from "./ghost-text-types";

// Re-export simulateSuggestion from the dedicated module (RULE-04)
export { simulateSuggestion } from "./ghost-text-suggestions";

// ── Internal Helper Functions ──────────────────────────────────────────────────

/** Stops the character-by-character streaming interval. */
export function stopStreaming(storage: GhostTextStorage): void {
  if (storage._streamTimer) {
    clearInterval(storage._streamTimer);
    storage._streamTimer = null;
  }
}

/** Cancels the auto-trigger debounce timer. */
export function cancelPendingAutoTrigger(storage: GhostTextStorage): void {
  if (storage._pendingTimer) {
    clearTimeout(storage._pendingTimer);
    storage._pendingTimer = null;
  }
}

/**
 * Clears all ghost text state: stops streaming, cancels pending requests
 * and auto-trigger timers, and resets storage values.
 * Does NOT clear the suggestion cache (performance-only data).
 */
export function clearAll(storage: GhostTextStorage, editor: Editor): void {
  stopStreaming(storage);
  cancelPendingAutoTrigger(storage);

  if (storage._abortController) {
    storage._abortController.abort();
    storage._abortController = null;
  }

  storage.currentSuggestion = null;
  storage.suggestionPos = null;
  storage._fullSuggestion = null;
  storage._isFetching = false;

  // Dispatch empty transaction to ensure decorations re-render
  if (!editor.isDestroyed) {
    editor.view.dispatch(editor.state.tr);
  }
}

/** Evicts oldest cache entries when the cache exceeds maxSize (LRU via Map insertion order). */
export function evictCache(storage: GhostTextStorage): void {
  while (storage._cache.size > storage._cacheMaxSize) {
    const firstKey = storage._cache.keys().next().value;
    if (firstKey !== undefined) storage._cache.delete(firstKey);
  }
}

/**
 * Begins character-by-character streaming of a suggestion.
 * Each tick reveals one more character from the full suggestion text.
 */
export function startStreaming(
  storage: GhostTextStorage,
  editor: Editor,
  suggestion: string,
): void {
  stopStreaming(storage);

  storage._fullSuggestion = suggestion;
  storage.currentSuggestion = "";
  storage.suggestionPos = editor.state.selection.head;
  storage._analytics.total++;

  let charIndex = 0;
  storage._streamTimer = setInterval(() => {
    if (editor.isDestroyed) {
      stopStreaming(storage);
      return;
    }

    // Stop streaming if cursor moved away
    if (editor.state.selection.head !== storage.suggestionPos) {
      clearAll(storage, editor);
      return;
    }

    charIndex++;
    if (charIndex > suggestion.length) {
      stopStreaming(storage);
      return;
    }

    storage.currentSuggestion = suggestion.slice(0, charIndex);
    editor.view.dispatch(editor.state.tr);
  }, 30);
}

/**
 * Handles a user keystroke while a ghost suggestion is displayed.
 *
 * - Single character matching the suggestion's first char → auto-advance
 *   (trim the first char from the full suggestion and keep remaining as ghost).
 * - Single character NOT matching → clear the suggestion entirely.
 * - Any other edit (paste, backspace, multi-char, edit at different position) → clear.
 */
export function handleTypingDuringSuggestion(
  storage: GhostTextStorage,
  editor: Editor,
  transaction: Transaction,
): void {
  const { suggestionPos, _fullSuggestion } = storage;
  if (!_fullSuggestion) {
    clearAll(storage, editor);
    return;
  }

  // Examine the first step only — multi-step operations (paste, IME, undo/redo)
  // always clear the suggestion.
  const step = transaction.steps[0];
  if (step instanceof ReplaceStep) {
    // Single-character insert at the suggestion anchor position
    if (step.from === suggestionPos && step.to === suggestionPos) {
      const slice = step.slice;
      const inserted = slice.content.textBetween(0, slice.content.size) ?? "";

      if (inserted.length === 1) {
        const firstChar = _fullSuggestion[0];

        if (inserted === firstChar) {
          // ── Auto-advance: user typed the expected character ──────────
          stopStreaming(storage);
          const remaining = _fullSuggestion.slice(1);

          if (remaining.length === 0) {
            clearAll(storage, editor);
            return;
          }

          storage._fullSuggestion = remaining;
          storage.currentSuggestion = remaining;
          // Cursor advanced by 1; update anchor to match
          storage.suggestionPos = suggestionPos + 1;
          return; // Keep showing remaining ghost text
        }

        // ── Mismatch: user typed a different character ────────────────
        storage._analytics.rejected++;
        clearAll(storage, editor);
        return;
      }
    }
  }

  // Any other edit at any position → clear
  clearAll(storage, editor);
}

/**
 * Schedules an auto-trigger after `suggestionDelay` ms of inactivity.
 *
 * Only activates when:
 * - The extension is enabled (storage._enabled)
 * - No suggestion is currently displayed
 * - The cursor is at the end of a paragraph
 * - There are at least `minChars` characters before the cursor
 */
export function scheduleAutoTrigger(
  storage: GhostTextStorage,
  editor: Editor,
  options: GhostTextOptions,
): void {
  if (!storage._enabled || editor.isDestroyed) return;
  if (storage.currentSuggestion !== null) return;

  const state = editor.state;
  const { $head } = state.selection;

  // Only trigger at the end of a paragraph (cursor at block end)
  if ($head.pos !== $head.end()) return;

  const textBefore = $head.parent.textContent.slice(0, $head.parentOffset);

  if (textBefore.length < (options.minChars ?? 5)) return;

  const delay = storage._suggestionDelay ?? options.suggestionDelay ?? 800;
  storage._pendingTimer = setTimeout(async () => {
    if (editor.isDestroyed) return;
    if (storage.currentSuggestion !== null) return;

    // Re-read text at trigger time (cursor might have moved)
    const currentState = editor.state;
    const currentHead = currentState.selection.$head;
    const currentBefore = currentHead.parent.textContent.slice(0, currentHead.parentOffset);
    const currentAfter = currentHead.parent.textContent.slice(currentHead.parentOffset);

    await fetchAndStreamSuggestion(storage, editor, options, currentBefore, currentAfter);
  }, delay);
}

/**
 * Calls fetchSuggestion and starts streaming the result.
 * Aborts any existing pending request before starting a new one.
 * Uses prefix-based cache to skip redundant API calls.
 */
export async function fetchAndStreamSuggestion(
  storage: GhostTextStorage,
  editor: Editor,
  options: GhostTextOptions,
  textBefore: string,
  textAfter: string,
): Promise<void> {
  // Abort any existing pending request
  if (storage._abortController) {
    storage._abortController.abort();
  }

  // ── Cache lookup ──────────────────────────────────────────────────────
  const cached = storage._cache.get(textBefore);
  if (cached && Date.now() - cached.timestamp < storage._cacheMaxAge) {
    if (editor.isDestroyed) return;
    startStreaming(storage, editor, cached.text);
    return;
  }

  const abortController = new AbortController();
  storage._abortController = abortController;

  // ── Show visible fetching status until the suggestion arrives ─────────
  // Anchor the status decoration at the current cursor position so the user
  // sees immediate feedback (§16.3, CR-AUFG-07-10).
  storage._isFetching = true;
  storage.suggestionPos = editor.state.selection.head;
  if (!editor.isDestroyed) {
    editor.view.dispatch(editor.state.tr);
  }

  const fetchFn = options.fetchSuggestion ?? simulateSuggestion;

  try {
    const suggestion = await fetchFn({
      textBefore,
      textAfter,
      signal: abortController.signal,
    });

    if (abortController.signal.aborted || editor.isDestroyed) return;

    // ── Store in cache ─────────────────────────────────────────────────
    storage._cache.set(textBefore, { text: suggestion, timestamp: Date.now() });
    evictCache(storage);

    startStreaming(storage, editor, suggestion);
  } catch (err) {
    // Silently ignore aborted requests (user typed before suggestion arrived)
    if (err instanceof DOMException && err.name === "AbortError") return;
    // For other unexpected errors, clear state as a safety measure
    clearAll(storage, editor);
  } finally {
    storage._isFetching = false;
    if (storage._abortController === abortController) {
      storage._abortController = null;
    }
    // Re-render decorations so the status indicator disappears
    if (!editor.isDestroyed) {
      editor.view.dispatch(editor.state.tr);
    }
  }
}

/**
 * Accepts the full suggestion, inserting it as real document content.
 * Uses _fullSuggestion (the complete text from fetchSuggestion) if available,
 * falling back to currentSuggestion (partial if mid-stream).
 *
 * Returns true if a suggestion was accepted, false if none was active.
 */
export function acceptSuggestion(storage: GhostTextStorage, editor: Editor): boolean {
  const fullText = storage._fullSuggestion ?? storage.currentSuggestion;
  if (!fullText) return false;

  storage._analytics.accepted++;
  clearAll(storage, editor);
  editor.commands.insertContent(fullText);
  return true;
}

/**
 * Accepts only the first "word" of the suggestion.
 *
 * The first word is defined as optional leading whitespace followed by
 * a sequence of non-whitespace characters. After insertion, the remaining
 * suggestion stays as ghost text at the new cursor position.
 *
 * Returns true if a word was accepted, false if no suggestion was active.
 */
export function acceptFirstWord(storage: GhostTextStorage, editor: Editor): boolean {
  const full = storage._fullSuggestion ?? storage.currentSuggestion;
  if (!full || full.length === 0) return false;

  // Match leading whitespace + first word (e.g., " stood" from " stood at the end…")
  const match = full.match(/^\s*\S+/);
  if (!match) {
    // Pure whitespace suggestion — just insert the whole thing
    storage._analytics.accepted++;
    clearAll(storage, editor);
    editor.commands.insertContent(full);
    return true;
  }

  const firstWord = match[0];
  const remaining = full.slice(firstWord.length);

  // Clear state BEFORE insertContent to prevent onUpdate from double-processing
  stopStreaming(storage);
  storage.currentSuggestion = null;
  storage.suggestionPos = null;
  storage._fullSuggestion = null;

  cancelPendingAutoTrigger(storage);

  // Insert the first word (synchronous — triggers onUpdate internally)
  editor.commands.insertContent(firstWord);

  // Cancel auto-trigger that onUpdate(insertContent) might have scheduled
  cancelPendingAutoTrigger(storage);

  // Set remaining suggestion as ghost text at the updated cursor position
  if (remaining.length > 0) {
    storage._fullSuggestion = remaining;
    storage.currentSuggestion = remaining;
    storage.suggestionPos = editor.state.selection.head;
    editor.view.dispatch(editor.state.tr);
  }

  storage._analytics.accepted++;
  return true;
}

/** Releases all resources: timers and pending requests. Does NOT clear cache. */
export function cleanup(storage: GhostTextStorage): void {
  stopStreaming(storage);
  cancelPendingAutoTrigger(storage);

  if (storage._abortController) {
    storage._abortController.abort();
    storage._abortController = null;
  }

  storage.currentSuggestion = null;
  storage.suggestionPos = null;
  storage._fullSuggestion = null;
  storage._isFetching = false;
}
