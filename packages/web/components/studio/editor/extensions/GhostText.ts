/**
 * GhostText — TipTap Extension for inline AI suggestions (Ghost Text / Copilot-style).
 *
 * Phase 1: Static Decoration Validation
 *   - Renders gray italic ghost text at cursor position via ProseMirror DecorationSet
 *   - Exposes setGhostText / clearGhostText on storage for test hooks
 *
 * Phase 2: Accept/Reject + Simulated Streaming (current)
 *   - Extension options with fetchSuggestion callback
 *   - Built-in simulated suggestion generator (trigger-based completions)
 *   - Character-by-character streaming via setInterval (30ms per char)
 *   - Keyboard shortcuts: Tab (accept all), Escape (clear), ArrowRight (first word)
 *   - Typing mismatch detection: matching char auto-advances, mismatch clears
 *   - Auto-trigger: pause detection (>800ms) after ≥5 chars at end of paragraph
 *   - AbortController-based cancellation for pending requests
 *
 * Phase 3: Real SSE streaming (future)
 *   - Connect fetchSuggestion to backend SSE endpoint
 *
 * Architecture decision (per ASSESS-001, §8):
 * Uses `Decoration.widget()` with `side: 1` — simplest correct approach
 * that places ghost text after the cursor without affecting document content.
 */

import { type Editor, Extension } from "@tiptap/core";
import { type EditorState, Plugin, PluginKey, type Transaction } from "@tiptap/pm/state";
import { ReplaceStep } from "@tiptap/pm/transform";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

// ── Interfaces ─────────────────────────────────────────────────────────────────

export interface GhostTextOptions {
  /** Called when a suggestion should be fetched.
   *  Phase 2: uses simulated local generator (built-in default).
   *  Phase 3: connects to real SSE endpoint. */
  fetchSuggestion?: (params: {
    textBefore: string;
    textAfter: string;
    signal: AbortSignal;
  }) => Promise<string>;
  /** Delay in ms before auto-triggering a suggestion after user pauses typing. */
  suggestionDelay?: number;
  /** Minimum characters before auto-triggering. */
  minChars?: number;
  /** Whether ghost text functionality is enabled. */
  enabled?: boolean;
}

export interface GhostTextStorage {
  /** The currently displayed suggestion text (partial if still streaming), or null */
  currentSuggestion: string | null;
  /** The cursor position (doc-relative) where the suggestion was anchored */
  suggestionPos: number | null;
  /** The full suggestion text returned by fetchSuggestion (for Tab accept) */
  _fullSuggestion: string | null;
  /** AbortController for the pending fetchSuggestion call */
  _abortController: AbortController | null;
  /** setInterval timer for character-by-character streaming */
  _streamTimer: ReturnType<typeof setInterval> | null;
  /** setTimeout timer for auto-trigger debounce */
  _pendingTimer: ReturnType<typeof setTimeout> | null;

  /** Test hook — programmatically set ghost text at current cursor position */
  setGhostText: (suggestion: string) => void;
  /** Test hook — clear ghost text */
  clearGhostText: () => void;
}

// ── Simulated Suggestion Generator (Phase 2 Built-in) ─────────────────────────

export async function simulateSuggestion(params: {
  textBefore: string;
  textAfter: string;
  signal: AbortSignal;
}): Promise<string> {
  const { textBefore, signal } = params;

  // Simulate AI inference latency (300-600ms)
  const delay = 300 + Math.random() * 300;
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, delay);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });

  if (signal.aborted) throw new DOMException("Aborted", "AbortError");

  // Trigger-based completions. Leading space provides natural gap between
  // the user's last word and the suggestion.
  const trimmed = textBefore.trimEnd();
  if (trimmed.endsWith("The old house")) {
    return " stood at the end of the lane, its windows dark.";
  }
  if (trimmed.endsWith("She walked")) {
    return " slowly towards the door, her footsteps echoing.";
  }
  if (trimmed.endsWith("It was a")) {
    return " cold and misty morning when they finally arrived.";
  }

  return " continued on their journey through the dark forest.";
}

// ── Internal Helper Functions ──────────────────────────────────────────────────
// All internal logic lives in module-level functions that operate on the
// extension's explicit context (storage, editor, options). This avoids
// TypeScript issues with private methods on the Extension.create() config object.

/** Stops the character-by-character streaming interval. */
function stopStreaming(storage: GhostTextStorage): void {
  if (storage._streamTimer) {
    clearInterval(storage._streamTimer);
    storage._streamTimer = null;
  }
}

/** Cancels the auto-trigger debounce timer. */
function cancelPendingAutoTrigger(storage: GhostTextStorage): void {
  if (storage._pendingTimer) {
    clearTimeout(storage._pendingTimer);
    storage._pendingTimer = null;
  }
}

/**
 * Clears all ghost text state: stops streaming, cancels pending requests
 * and auto-trigger timers, and resets storage values.
 */
function clearAll(storage: GhostTextStorage, editor: Editor): void {
  stopStreaming(storage);
  cancelPendingAutoTrigger(storage);

  if (storage._abortController) {
    storage._abortController.abort();
    storage._abortController = null;
  }

  storage.currentSuggestion = null;
  storage.suggestionPos = null;
  storage._fullSuggestion = null;

  // Dispatch empty transaction to ensure decorations re-render
  if (!editor.isDestroyed) {
    editor.view.dispatch(editor.state.tr);
  }
}

/**
 * Begins character-by-character streaming of a suggestion.
 * Each tick reveals one more character from the full suggestion text.
 */
function startStreaming(storage: GhostTextStorage, editor: Editor, suggestion: string): void {
  stopStreaming(storage);

  storage._fullSuggestion = suggestion;
  storage.currentSuggestion = "";
  storage.suggestionPos = editor.state.selection.head;

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
function handleTypingDuringSuggestion(
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
 * - The extension is enabled
 * - No suggestion is currently displayed
 * - The cursor is at the end of a paragraph
 * - There are at least `minChars` characters before the cursor
 */
function scheduleAutoTrigger(
  storage: GhostTextStorage,
  editor: Editor,
  options: GhostTextOptions,
): void {
  if (!options.enabled || editor.isDestroyed) return;
  if (storage.currentSuggestion !== null) return;

  const state = editor.state;
  const { $head } = state.selection;

  // Only trigger at the end of a paragraph (cursor at block end)
  if ($head.pos !== $head.end()) return;

  const textBefore = $head.parent.textContent.slice(0, $head.parentOffset);

  if (textBefore.length < (options.minChars ?? 5)) return;

  const delay = options.suggestionDelay ?? 800;
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
 */
async function fetchAndStreamSuggestion(
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

  const abortController = new AbortController();
  storage._abortController = abortController;

  const fetchFn = options.fetchSuggestion ?? simulateSuggestion;

  try {
    const suggestion = await fetchFn({
      textBefore,
      textAfter,
      signal: abortController.signal,
    });

    if (abortController.signal.aborted || editor.isDestroyed) return;

    startStreaming(storage, editor, suggestion);
  } catch (err) {
    // Silently ignore aborted requests (user typed before suggestion arrived)
    if (err instanceof DOMException && err.name === "AbortError") return;
    // For other unexpected errors, clear state as a safety measure
    clearAll(storage, editor);
  } finally {
    if (storage._abortController === abortController) {
      storage._abortController = null;
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
function acceptSuggestion(storage: GhostTextStorage, editor: Editor): boolean {
  const fullText = storage._fullSuggestion ?? storage.currentSuggestion;
  if (!fullText) return false;

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
function acceptFirstWord(storage: GhostTextStorage, editor: Editor): boolean {
  const full = storage._fullSuggestion ?? storage.currentSuggestion;
  if (!full || full.length === 0) return false;

  // Match leading whitespace + first word (e.g., " stood" from " stood at the end…")
  const match = full.match(/^\s*\S+/);
  if (!match) {
    // Pure whitespace suggestion — just insert the whole thing
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

  return true;
}

/** Releases all resources: timers and pending requests. */
function cleanup(storage: GhostTextStorage): void {
  stopStreaming(storage);
  cancelPendingAutoTrigger(storage);

  if (storage._abortController) {
    storage._abortController.abort();
    storage._abortController = null;
  }

  storage.currentSuggestion = null;
  storage.suggestionPos = null;
  storage._fullSuggestion = null;
}

// ── Extension ──────────────────────────────────────────────────────────────────

export const GhostText = Extension.create<GhostTextOptions, GhostTextStorage>({
  name: "ghostText",

  addOptions() {
    return {
      fetchSuggestion: simulateSuggestion,
      suggestionDelay: 800,
      minChars: 5,
      enabled: true,
    };
  },

  addStorage() {
    return {
      currentSuggestion: null as string | null,
      suggestionPos: null as number | null,
      _fullSuggestion: null as string | null,
      _abortController: null as AbortController | null,
      _streamTimer: null as ReturnType<typeof setInterval> | null,
      _pendingTimer: null as ReturnType<typeof setTimeout> | null,
      setGhostText: () => {},
      clearGhostText: () => {},
    };
  },

  onBeforeCreate() {
    // ── Bind test hooks ──────────────────────────────────────────────────
    // Must happen here because `this.editor` is not available during addStorage().

    this.storage.setGhostText = (suggestion: string) => {
      if (this.editor.isDestroyed) return;
      this.storage.currentSuggestion = suggestion;
      this.storage._fullSuggestion = suggestion;
      this.storage.suggestionPos = this.editor.state.selection.head;
      // Dispatch empty transaction to trigger decoration re-evaluation
      this.editor.view.dispatch(this.editor.state.tr);
    };

    this.storage.clearGhostText = () => {
      clearAll(this.storage, this.editor);
    };
  },

  // ── Keyboard Shortcuts ────────────────────────────────────────────────

  addKeyboardShortcuts() {
    const storage = this.storage;
    const editor = this.editor;

    return {
      Tab: () => acceptSuggestion(storage, editor),
      Escape: () => {
        clearAll(storage, editor);
        return true;
      },
      ArrowRight: () => acceptFirstWord(storage, editor),
    };
  },

  // ── Lifecycle Hooks ───────────────────────────────────────────────────

  onUpdate({ transaction }: { transaction: Transaction }) {
    if (!transaction.docChanged) return;

    // ── Handle user typing while a suggestion is active ──────────────
    if (this.storage.currentSuggestion !== null) {
      handleTypingDuringSuggestion(this.storage, this.editor, transaction);

      // If suggestion is still active (auto-advanced), re-render decorations
      // and return — don't schedule a new auto-trigger.
      if (this.storage.currentSuggestion !== null) {
        this.editor.view.dispatch(this.editor.state.tr);
        return;
      }
      // If cleared by mismatch handling, fall through to schedule auto-trigger
    } else {
      // No suggestion active but a request is still pending: cancel it.
      if (this.storage._abortController) {
        this.storage._abortController.abort();
        this.storage._abortController = null;
      }
    }

    // Schedule auto-trigger for new content (debounced on every keystroke)
    cancelPendingAutoTrigger(this.storage);
    scheduleAutoTrigger(this.storage, this.editor, this.options);
  },

  onDestroy() {
    cleanup(this.storage);
  },

  // ── ProseMirror Plugin (Decoration Rendering) ──────────────────────

  addProseMirrorPlugins() {
    const extension = this;

    return [
      new Plugin({
        key: new PluginKey("ghostText"),
        props: {
          decorations(state: EditorState) {
            const { currentSuggestion, suggestionPos } = extension.storage;

            if (!currentSuggestion || suggestionPos === null) {
              return DecorationSet.empty;
            }

            // Hide ghost if cursor has moved away from the anchor position
            if (state.selection.head !== suggestionPos) {
              return DecorationSet.empty;
            }

            // Build the ghost text DOM element
            const ghostSpan = document.createElement("span");
            ghostSpan.textContent = currentSuggestion;
            ghostSpan.className = "ghost-text-suggestion";
            ghostSpan.setAttribute("aria-hidden", "true");

            return DecorationSet.create(state.doc, [
              Decoration.widget(suggestionPos, ghostSpan, {
                side: 1,
                key: "ghost",
              }),
            ]);
          },
        },
      }),
    ];
  },
});
