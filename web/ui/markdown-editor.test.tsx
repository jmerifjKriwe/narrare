// @vitest-environment jsdom
/**
 * The shared Markdown editor contract, driven through the real TipTap: the
 * `value` arrives as Markdown and renders as rich text (heading, emphasis),
 * every update emits the document back as Markdown — the format the store
 * carries from this editor on — and the editable element is a real labelled
 * textbox (role, multiline, aria-label from the `label` prop), the same
 * contract the chapter editor carries today.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Editor } from "@tiptap/core";
import { afterEach, describe, expect, it } from "vitest";

import { MarkdownEditor } from "./markdown-editor";

// jsdom lays out nothing: Element geometry reports zeros, but Range geometry
// is simply missing — and ProseMirror reads Range rects whenever it scrolls
// a selection into view (after typing, after focus). Hand it the same zeros
// the elements already claim, so "nothing to scroll" is the only answer.
const zeroRect = { top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, x: 0, y: 0 } as DOMRect;
Range.prototype.getClientRects = function (): DOMRectList {
  return [zeroRect] as unknown as DOMRectList;
};
Range.prototype.getBoundingClientRect = () => zeroRect;

afterEach(cleanup);

describe("MarkdownEditor", () => {
  it("renders markdown as rich text and emits markdown on change", async () => {
    const emitted: string[] = [];
    let editor: Editor | null = null;
    render(
      <MarkdownEditor
        label="Kapiteltext"
        value={"# Titel\n\nEin *kurzer* Absatz."}
        onChange={(markdown) => emitted.push(markdown)}
        onReady={(instance) => {
          editor = instance;
        }}
      />,
    );

    // The Markdown arrived as structure, not as literal source: a real
    // heading and a real emphasis, never a `#` or `*` on screen.
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Titel");
    expect(screen.getByText("kurzer").closest("em")).not.toBeNull();

    // Typing is the user's edit; what the store receives is Markdown — the
    // whole document, exactly the source this editor owns. The caret goes to
    // the end through the live instance (a bare `.focus()` would leave the
    // selection where jsdom last had it, and the edit must not be
    // positional).
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    (await screen.findByRole("textbox", { name: "Kapiteltext" })).focus();
    await waitFor(() => expect(editor).not.toBeNull());
    editor!.commands.focus("end");
    await user.keyboard(" Noch ein Satz.");

    await waitFor(() => expect(emitted.length).toBeGreaterThan(0));
    // The emitted body is the document as Markdown source: heading and
    // emphasis survive as `#`/`*`, the typed words appended, no HTML tags.
    expect(emitted.at(-1)).toBe("# Titel\n\nEin *kurzer* Absatz. Noch ein Satz.");
  });

  it("carries the aria label", async () => {
    render(<MarkdownEditor label="Beschreibung" value="" onChange={() => {}} />);

    const box = await screen.findByRole("textbox", { name: "Beschreibung" });
    expect(box.getAttribute("aria-multiline")).toBe("true");
    expect(box.classList.contains("prose")).toBe(true);
  });
});
