/**
 * GhostText — TipTap Extension for inline AI suggestions (Ghost Text / Copilot-style).
 *
 * Phase 1: Static Decoration Validation
 *   - Renders gray italic ghost text at cursor position via ProseMirror DecorationSet
 *   - Exposes setGhostText / clearGhostText on storage for test hooks
 *
 * Phase 2: Accept/Reject + Simulated Streaming
 *   - Extension options with fetchSuggestion callback
 *   - Built-in simulated suggestion generator (trigger-based completions)
 *   - Character-by-character streaming via setInterval (30ms per char)
 *   - Keyboard shortcuts: Tab (accept all), Escape (clear), ArrowRight (first word)
 *   - Typing mismatch detection: matching char auto-advances, mismatch clears
 *   - Auto-trigger: pause detection (>800ms) after ≥5 chars at end of paragraph
 *   - AbortController-based cancellation for pending requests
 *
 * Phase 3: Real SSE streaming
 *   - Connect fetchSuggestion to backend SSE endpoint
 *
 * Phase 4: Production Polish
 *   - Prefix-based suggestion cache (LRU eviction, avoids redundant API calls)
 *   - Keyboard shortcut hint decoration (Tab accept · Esc dismiss · → word)
 *   - Runtime configuration: setEnabled / setDelay for reactive toggling
 *   - Minimal analytics counters (accepted / rejected / total)
 *
 * Architecture decision (per ASSESS-001, §8):
 * Uses `Decoration.widget()` with `side: 1` — simplest correct approach
 * that places ghost text after the cursor without affecting document content.
 */

import { Extension } from "@tiptap/core";
import { type EditorState, Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

// ── Re-export shared types (consumers import from this module) ────────────────
export type { GhostTextOptions, GhostTextStorage } from "./ghost-text-types";

// ── Import internal helpers ───────────────────────────────────────────────────
import {
  acceptFirstWord,
  acceptSuggestion,
  cancelPendingAutoTrigger,
  cleanup,
  clearAll,
  handleTypingDuringSuggestion,
  scheduleAutoTrigger,
} from "./ghost-text-helpers";
import { simulateSuggestion } from "./ghost-text-suggestions";

// Re-export simulateSuggestion for external consumers (TipTapEditor.tsx)
export { simulateSuggestion } from "./ghost-text-suggestions";

// ── Extension ──────────────────────────────────────────────────────────────────

import type { GhostTextOptions, GhostTextStorage } from "./ghost-text-types";

export const GhostText = Extension.create<GhostTextOptions, GhostTextStorage>({
  name: "ghostText",

  addOptions() {
    return {
      fetchSuggestion: simulateSuggestion,
      suggestionDelay: 800,
      minChars: 5,
      enabled: true,
      // Localized via i18n by TipTapEditorController (`t("ghostText.hint")`).
      // Empty default — no hardcoded English (RULE-16, Check 12).
      hintText: "",
      fetchingStatusText: "",
      errorStatusText: "",
      errorStatusDurationMs: 4000,
    };
  },

  addStorage() {
    return {
      currentSuggestion: null as string | null,
      suggestionPos: null as number | null,
      _fullSuggestion: null as string | null,
      _abortController: null as AbortController | null,
      _isFetching: false as boolean,
      _streamTimer: null as ReturnType<typeof setInterval> | null,
      _pendingTimer: null as ReturnType<typeof setTimeout> | null,

      _enabled: true,
      _suggestionDelay: 800,

      _cache: new Map<string, { text: string; timestamp: number }>(),
      _cacheMaxAge: 30_000,
      _cacheMaxSize: 50,

      _analytics: { accepted: 0, rejected: 0, total: 0 } as {
        accepted: number;
        rejected: number;
        total: number;
      },

      _errorStatusVisible: false as boolean,
      _errorTimer: null as ReturnType<typeof setTimeout> | null,

      setGhostText: () => {},
      clearGhostText: () => {},
      setEnabled: (_enabled: boolean) => {},
      setDelay: (_delay: number) => {},
      getAnalytics: () => ({ accepted: 0, rejected: 0, total: 0 }),
    };
  },

  onBeforeCreate() {
    // ── Bind test hooks and runtime methods ────────────────────────────
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

    this.storage.setEnabled = (enabled: boolean) => {
      this.storage._enabled = enabled;
      if (!enabled) {
        clearAll(this.storage, this.editor);
      }
    };

    this.storage.setDelay = (delay: number) => {
      this.storage._suggestionDelay = delay;
    };

    this.storage.getAnalytics = () => ({ ...this.storage._analytics });
  },

  // ── Keyboard Shortcuts ────────────────────────────────────────────────

  addKeyboardShortcuts() {
    const storage = this.storage;
    const editor = this.editor;

    return {
      Tab: () => acceptSuggestion(storage, editor),
      Escape: () => {
        if (storage.currentSuggestion !== null) {
          storage._analytics.rejected++;
        }
        clearAll(storage, editor);
        return true;
      },
      ArrowRight: () => acceptFirstWord(storage, editor),
    };
  },

  // ── Lifecycle Hooks ───────────────────────────────────────────────────

  onUpdate({ transaction }: { transaction: import("@tiptap/pm/state").Transaction }) {
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
            const { currentSuggestion, suggestionPos, _isFetching, _errorStatusVisible } =
              extension.storage;

            // ── Fetching status indicator (before suggestion arrives) ──────
            // Shown while a suggestion request is in-flight so the user gets
            // immediate visual feedback (§16.3, CR-AUFG-07-10). The visible
            // text comes from the React-controlled `fetchingStatusText`
            // option (ADR-043 Note 7) — never hardcoded English.
            if (
              _isFetching &&
              !currentSuggestion &&
              suggestionPos !== null &&
              state.selection.head === suggestionPos
            ) {
              const statusText = extension.options.fetchingStatusText ?? "";
              if (statusText) {
                const fetchSpan = document.createElement("span");
                fetchSpan.textContent = statusText;
                fetchSpan.className = "ghost-text-fetching";
                fetchSpan.setAttribute("aria-hidden", "true");
                return DecorationSet.create(state.doc, [
                  Decoration.widget(suggestionPos, fetchSpan, {
                    side: 1,
                    key: "ghost-fetching",
                  }),
                ]);
              }
            }

            // ── Transient error status (after non-AbortError fetch failure) ──
            // Low-noise, non-blocking decoration shown only when:
            // - _errorStatusVisible is set (by showErrorStatus helper)
            // - not currently fetching (no overlap with fetching indicator)
            // - no current suggestion (no overlap with ghost text)
            // - cursor remains at the anchor position
            // (CR-AUFG-07-15). Visible text comes from the React-controlled
            // `errorStatusText` option — never hardcoded English.
            if (
              _errorStatusVisible &&
              !_isFetching &&
              !currentSuggestion &&
              suggestionPos !== null &&
              state.selection.head === suggestionPos
            ) {
              const errorText = extension.options.errorStatusText ?? "";
              if (errorText) {
                const errorSpan = document.createElement("span");
                errorSpan.textContent = errorText;
                errorSpan.className = "ghost-text-error";
                errorSpan.setAttribute("aria-hidden", "true");
                return DecorationSet.create(state.doc, [
                  Decoration.widget(suggestionPos, errorSpan, {
                    side: 1,
                    key: "ghost-error",
                  }),
                ]);
              }
            }

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

            // Build the keyboard shortcut hint (fades in via CSS).
            // Text comes from the React-controlled `hintText` option
            // (ADR-043 Note 7) — never hardcoded English.
            const hintSpan = document.createElement("span");
            hintSpan.textContent = extension.options.hintText ?? "";
            hintSpan.className = "ghost-text-hint";
            hintSpan.setAttribute("aria-hidden", "true");

            return DecorationSet.create(state.doc, [
              Decoration.widget(suggestionPos, ghostSpan, {
                side: 1,
                key: "ghost",
              }),
              Decoration.widget(suggestionPos, hintSpan, {
                side: 1,
                key: "ghost-hint",
              }),
            ]);
          },
        },
      }),
    ];
  },
});
