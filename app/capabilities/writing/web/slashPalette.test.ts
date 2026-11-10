// @vitest-environment jsdom
/**
 * The slash door's two guards, driven through a headless editor: a
 * whitespace-only paragraph still opens the palette (a stray space is not
 * prose), and a range selection never does (a range is a replacement, not
 * the door — even when it starts at offset 0 of an empty paragraph). The
 * key travels the same road as in the mounted editor — the plugin's
 * `handleKeyDown` via the view's `someProp` — with the selection placed
 * programmatically, because jsdom performs no arrow-key caret motion.
 */
import { afterEach, describe, expect, it } from "vitest";
import { Editor } from "@tiptap/core";
import { TextSelection } from "@tiptap/pm/state";
import StarterKit from "@tiptap/starter-kit";

import { PALETTE_OPEN_EVENT } from "@shell/lib/palette";

import { slashPalette } from "./slashPalette";

let editor: Editor | null = null;

afterEach(() => {
  editor?.destroy();
  editor = null;
});

/** Press `/` the way ProseMirror asks plugins: first truthy answer wins. */
function pressSlash(view: Editor["view"]): unknown {
  const event = new KeyboardEvent("keydown", { key: "/" });
  return view.someProp("handleKeyDown", (handler) =>
    (handler as (view: Editor["view"], event: KeyboardEvent) => boolean)(view, event),
  );
}

describe("slashPalette's guards", () => {
  it("opens from a whitespace-only paragraph and inserts nothing", () => {
    // A non-breaking space survives parsing where a plain space is trimmed,
    // so the paragraph reads whitespace-only, not empty.
    editor = new Editor({ extensions: [StarterKit, slashPalette()], content: "<p>\u00a0</p>" });
    editor.view.dispatch(
      editor.state.tr.setSelection(TextSelection.create(editor.state.doc, 1)),
    );
    const seen: string[] = [];
    const onRequest = (event: Event) => {
      seen.push((event as CustomEvent<{ query: string }>).detail.query);
    };
    window.addEventListener(PALETTE_OPEN_EVENT, onRequest);
    try {
      expect(pressSlash(editor.view)).toBe(true);
      expect(seen).toEqual(["/"]);
    } finally {
      window.removeEventListener(PALETTE_OPEN_EVENT, onRequest);
    }
  });

  it("a range starting at offset 0 of an empty paragraph stays literal", () => {
    // The range spans the empty paragraph into the next: its start reads
    // exactly like the door, but the selection is not collapsed.
    editor = new Editor({ extensions: [StarterKit, slashPalette()], content: "<p></p><p>a</p>" });
    const selection = TextSelection.create(editor.state.doc, 1, 4);
    expect(selection.empty).toBe(false);
    expect(selection.$from.parentOffset).toBe(0);
    editor.view.dispatch(editor.state.tr.setSelection(selection));
    const seen: string[] = [];
    const onRequest = (event: Event) => {
      seen.push((event as CustomEvent<{ query: string }>).detail.query);
    };
    window.addEventListener(PALETTE_OPEN_EVENT, onRequest);
    try {
      expect(pressSlash(editor.view)).toBeFalsy();
      expect(seen).toEqual([]);
    } finally {
      window.removeEventListener(PALETTE_OPEN_EVENT, onRequest);
    }
  });
});
