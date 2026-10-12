/**
 * selectionContext tests — context extraction honors the backend cap.
 *
 * Audit B01 regression: the rewrite flow extracted an 800-char radius while
 * the backend caps context_before/context_after at 500 chars (guaranteed 422).
 *
 * @module selectionContext.test
 */

import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";
import { AI_CONTEXT_RADIUS_CHARS, getSelectionContext } from "../selectionContext";

function createTestEditor(content: string): Editor {
  const element = document.createElement("div");
  document.body.appendChild(element);
  return new Editor({ element, extensions: [StarterKit], content });
}

describe("getSelectionContext", () => {
  it("clamps context to the 500-char backend cap on both sides", () => {
    const editor = createTestEditor(`<p>${"a".repeat(2000)}</p>`);
    editor.commands.setTextSelection({ from: 1000, to: 1100 });

    const { contextBefore, contextAfter } = getSelectionContext(editor, 1000, 1100);

    expect(contextBefore.length).toBe(AI_CONTEXT_RADIUS_CHARS);
    expect(contextAfter.length).toBe(AI_CONTEXT_RADIUS_CHARS);
    expect(contextBefore).toBe("a".repeat(AI_CONTEXT_RADIUS_CHARS));
    editor.destroy();
  });

  it("returns shorter context near the document edges without crashing", () => {
    const editor = createTestEditor("<p>Hello selection world</p>");
    const { contextBefore } = getSelectionContext(editor, 1, 6);

    expect(contextBefore.length).toBeLessThanOrEqual(AI_CONTEXT_RADIUS_CHARS);
    editor.destroy();
  });
});
