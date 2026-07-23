/**
 * useEditorSelectionText — live editor text-selection subscription.
 *
 * The Dialogue Coach panel (ASSIST-004) needs the *current* TipTap selection so
 * the writer can pick a dialogue passage and run analysis on it. This hook
 * reuses the WRITE-004 rewrite accessor
 * (`editor.state.doc.textBetween(from, to, " ")`) and keeps the value live by
 * subscribing to `transaction` — mirroring useAnnotationMarkTracker /
 * useGhostTextOnboardingAnchor.
 *
 * These tests pin the contract: returns the selection text, returns null when
 * the selection is empty / no editor, and updates when the editor emits a
 * transaction.
 */
import { act, renderHook } from "@testing-library/react";
import type { Editor } from "@tiptap/react";
import { describe, expect, it } from "vitest";
import { useEditorSelectionText } from "../useEditorSelectionText";

/**
 * Mutable fake editor. Exposes the prosemirror-shape surface the hook reads
 * (`state.selection` + `state.doc.textBetween`) plus an event bus the hook
 * subscribes to (`on`/`off` + `emit`).
 */
function makeFakeEditor(initialSelection: string | null = null) {
  let current = initialSelection;
  const listeners = new Map<string, Set<() => void>>();

  const editor = {
    state: {
      get selection() {
        const len = current ? current.length : 0;
        return { from: 0, to: len, empty: len === 0 };
      },
      doc: {
        textBetween: (from: number, to: number) => {
          if (to <= from) return "";
          return current ? current.slice(0, to - from) : "";
        },
      },
    },
    on: (event: string, cb: () => void) => {
      let set = listeners.get(event);
      if (!set) {
        set = new Set();
        listeners.set(event, set);
      }
      set.add(cb);
    },
    off: (event: string, cb: () => void) => {
      listeners.get(event)?.delete(cb);
    },
  } as unknown as Editor;

  return {
    editor,
    /** Replace the editor's current selection text and fire `transaction`. */
    select(next: string | null) {
      current = next;
      for (const cb of listeners.get("transaction") ?? []) cb();
    },
  };
}

describe("useEditorSelectionText", () => {
  it("returns null when there is no editor", () => {
    const { result } = renderHook(() => useEditorSelectionText(null));
    expect(result.current).toBeNull();
  });

  it("returns the current selection text on mount", () => {
    const { editor } = makeFakeEditor('"I am sad."');
    const { result } = renderHook(() => useEditorSelectionText(editor));
    expect(result.current).toBe('"I am sad."');
  });

  it("returns null when the selection is empty (collapsed caret)", () => {
    const { editor } = makeFakeEditor(null);
    const { result } = renderHook(() => useEditorSelectionText(editor));
    expect(result.current).toBeNull();
  });

  it("updates when the editor selection changes via a transaction", () => {
    const fake = makeFakeEditor(null);
    const { result } = renderHook(() => useEditorSelectionText(fake.editor));
    expect(result.current).toBeNull();

    act(() => fake.select('"Hello."'));
    expect(result.current).toBe('"Hello."');

    act(() => fake.select(null));
    expect(result.current).toBeNull();
  });

  it("unsubscribes on unmount / editor change", () => {
    const fake = makeFakeEditor('"x"');
    const { unmount } = renderHook(() => useEditorSelectionText(fake.editor));
    unmount();
    // Emitting after unmount must not throw (handler removed).
    expect(() => act(() => fake.select('"y"'))).not.toThrow();
  });
});
