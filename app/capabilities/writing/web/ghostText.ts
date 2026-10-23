/**
 * The editor's ghost text: a continuation proposal rendered as a ProseMirror
 * decoration at the caret, never as document content.
 *
 * The distinction is the contract. The ghost lives in plugin state — where it
 * sits and what it says — and paints a widget into the editor DOM. The
 * document is not touched until Tab commits the text with a plain insertion
 * transaction; Esc drops the plugin state and nothing else. Because the
 * document never changes while a ghost is pending, no autosave can persist a
 * proposal its reader never accepted.
 */
import { Extension } from "@tiptap/core";
import type { Editor } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

/** The ghost's plugin state: the caret position it arrived at, its text. */
type Ghost = { pos: number; text: string };

/** Component → plugin transaction meta: the current proposal, null for none. */
type GhostMeta = { text: string | null };

export const ghostKey = new PluginKey<Ghost | null>("ghostText");

/** What the editor owes the world when a ghost is resolved. */
export type GhostHandlers = {
  onAccept(): void;
  onDiscard(): void;
};

/**
 * Set, grow, or clear the ghost. The position is captured once — the caret
 * at the moment the ghost first appears — and afterwards only ever mapped
 * through document changes, so typing around a ghost moves it with the text.
 */
export function showGhost(editor: Editor, text: string | null): void {
  editor.view.dispatch(editor.state.tr.setMeta(ghostKey, { text } satisfies GhostMeta));
}

/**
 * The TipTap extension carrying the plugin. It takes the component's handlers
 * REF, not the handlers themselves: the plugin is built once with the editor
 * and cannot be rebuilt per render, while the component keeps the ref current
 * — every resolution announces and resolves with the latest words.
 */
export function ghostText(handlers: { current: GhostHandlers }): Extension {
  return Extension.create({
    name: "ghostText",
    addProseMirrorPlugins() {
      return [
        new Plugin<Ghost | null>({
          key: ghostKey,
          state: {
            init: () => null,
            apply(tr, previous) {
              const meta = tr.getMeta(ghostKey) as GhostMeta | undefined;
              if (meta) {
                if (meta.text === null || meta.text === "") return null;
                return { pos: previous?.pos ?? tr.selection.from, text: meta.text };
              }
              if (!previous || !tr.docChanged) return previous;
              const mapped = tr.mapping.mapResult(previous.pos);
              return mapped.deleted ? null : { pos: mapped.pos, text: previous.text };
            },
          },
          props: {
            decorations(state) {
              const ghost = ghostKey.getState(state);
              if (!ghost) return null;
              // One widget span, aria-hidden: the live region carries the
              // arrival, and screen readers must not read uncommitted text
              // as document content.
              const span = document.createElement("span");
              span.className = "ghost text-muted italic";
              span.setAttribute("aria-hidden", "true");
              span.textContent = ghost.text;
              return DecorationSet.create(state.doc, [
                Decoration.widget(ghost.pos, span, { side: 1 }),
              ]);
            },
            handleKeyDown(view, event) {
              if (event.isComposing) return false;
              const ghost = ghostKey.getState(view.state);
              if (event.key === "Escape" && !ghost) {
                // Esc with no ghost is not the editor's key — but ProseMirror's
                // core capture marks every focused-editor Esc defaultPrevented
                // anyway, and the window handler reads that as "handled". Left
                // alone, a writer holding the caret could never step the focus
                // back. Forward a clean copy of the key upward: the phase-4
                // seam (stand down on defaultPrevented) stays intact, and the
                // ghost cases below still stop the event entirely.
                // event.currentTarget is the editor DOM here — dispatching the
                // copy there would re-enter this very handler. The window is
                // where the key is headed anyway: its propagation path holds
                // only the window, so the copy cannot come back down.
                window.dispatchEvent(
                  new KeyboardEvent("keydown", {
                    key: event.key,
                    bubbles: true,
                    cancelable: true,
                    repeat: event.repeat,
                    ctrlKey: event.ctrlKey,
                    metaKey: event.metaKey,
                    altKey: event.altKey,
                    shiftKey: event.shiftKey,
                  }),
                );
                return false;
              }
              if (!ghost) return false;
              if (event.key === "Tab") {
                // The commit: one insertion transaction, and the document
                // finally changes — onUpdate lets the debounced autosave
                // persist it like any typing would be.
                const tr = view.state.tr.insertText(ghost.text, ghost.pos);
                tr.setMeta(ghostKey, { text: null } satisfies GhostMeta);
                view.dispatch(tr);
                handlers.current.onAccept();
                return true;
              }
              if (event.key === "Escape") {
                // The seam: a ghost's Esc must never reach NovelPage's window
                // handler, which would step the focus instead of discarding.
                // ProseMirror preventDefaults a handled key; stopping the
                // propagation keeps it from the window entirely.
                event.preventDefault();
                event.stopPropagation();
                view.dispatch(view.state.tr.setMeta(ghostKey, { text: null } satisfies GhostMeta));
                handlers.current.onDiscard();
                return true;
              }
              return false;
            },
          },
        }),
      ];
    },
  });
}
