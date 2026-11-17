// @vitest-environment jsdom
/**
 * The scene editor (W4 Task 12) — the TipTap prose surface that replaces the
 * read-only paragraphs: a real labelled textbox, the body's paragraphs with
 * the draft's drop cap on the first, and a plain-text storage contract (the
 * scene body is prose, not Markdown — paragraphs joined by a blank line,
 * hard breaks by a single newline, the same shape the read-only port drew
 * and the server's whitespace rule counts). Content initializes once per
 * scene; a switch remounts (the page keys it), never resets a live caret.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { Editor } from "@tiptap/core";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { applyLocale } from "@shell/lib/locale";

import { SceneEditor, bodyToHtml } from "./SceneEditor";

beforeEach(() => {
  applyLocale("de");
});

afterEach(() => {
  cleanup();
});

/** Wait for the live instance (the editor mounts in an effect). */
async function editorOf(get: () => Editor | null): Promise<Editor> {
  await waitFor(() => {
    expect(get()).not.toBeNull();
  });
  return get() as Editor;
}

describe("bodyToHtml — the plain prose the editor initializes from", () => {
  it("blank lines separate paragraphs, single newlines are hard breaks", () => {
    expect(bodyToHtml("Erster Absatz.\n\nZweiter Absatz.")).toBe(
      "<p>Erster Absatz.</p><p>Zweiter Absatz.</p>",
    );
    expect(bodyToHtml("Zeile eins\nZeile zwei")).toBe("<p>Zeile eins<br>Zeile zwei</p>");
  });

  it("an empty body is one empty paragraph — no invented prose", () => {
    expect(bodyToHtml("")).toBe("<p></p>");
    expect(bodyToHtml("   \n\n  ")).toBe("<p></p>");
  });

  it("escapes the markup characters prose may carry", () => {
    expect(bodyToHtml("<x> & y")).toBe("<p>&lt;x&gt; &amp; y</p>");
  });
});

describe("the editing surface", () => {
  it("is a real labelled multiline textbox wearing the live prose class", async () => {
    render(<SceneEditor body="Ein Satz." onChange={() => {}} label="Szenenprosa" />);
    await screen.findByRole("textbox", { name: "Szenenprosa" });
    await waitFor(() => expect(screen.getByRole("textbox").textContent).toBe("Ein Satz."));
    const box = screen.getByRole("textbox");
    expect(box.getAttribute("aria-multiline")).toBe("true");
    expect(box.closest(".workspace-prose-live")).not.toBeNull();
  });

  it("renders the body's paragraphs, the first under the drop cap", async () => {
    render(
      <SceneEditor body={"Erster Absatz.\n\nZweiter Absatz."} onChange={() => {}} label="Prosa" />,
    );
    await screen.findByRole("textbox");
    await waitFor(() => expect(screen.getByRole("textbox").querySelectorAll("p")).toHaveLength(2));
    const box = screen.getByRole("textbox");
    const paragraphs = box.querySelectorAll("p");
    expect(paragraphs[0].textContent).toBe("Erster Absatz.");
    expect(paragraphs[1].textContent).toBe("Zweiter Absatz.");
    // The drop cap is the wrapper's first-paragraph rule (globals.css).
    expect(box.className).toContain("ProseMirror");
  });

  it("an empty body keeps the surface honest — one empty paragraph", async () => {
    render(<SceneEditor body="" onChange={() => {}} label="Prosa" />);
    await screen.findByRole("textbox");
    await waitFor(() => expect(screen.getByRole("textbox").querySelectorAll("p")).toHaveLength(1));
    expect(screen.getByRole("textbox").textContent).toBe("");
  });

  it("every edit emits the whole body as plain prose — paragraphs by blank line", async () => {
    const onChange = vi.fn();
    let instance: Editor | null = null;
    render(
      <SceneEditor
        body="Alt."
        onChange={onChange}
        label="Prosa"
        onReady={(editor) => {
          instance = editor;
        }}
      />,
    );
    const editor = await editorOf(() => instance);
    expect(onChange).not.toHaveBeenCalled();
    editor.commands.insertContentAt(
      { from: 0, to: editor.state.doc.content.size },
      "<p>Neu eins.</p><p>Neu zwei.</p>",
    );
    expect(onChange).toHaveBeenLastCalledWith("Neu eins.\n\nNeu zwei.");
  });

  it("a hard break serializes as a single newline, not a paragraph gap", async () => {
    const onChange = vi.fn();
    let instance: Editor | null = null;
    render(
      <SceneEditor
        body="Alt."
        onChange={onChange}
        label="Prosa"
        onReady={(editor) => {
          instance = editor;
        }}
      />,
    );
    const editor = await editorOf(() => instance);
    editor.commands.insertContentAt(
      { from: 0, to: editor.state.doc.content.size },
      "<p>Zeile eins<br>Zeile zwei</p>",
    );
    expect(onChange).toHaveBeenLastCalledWith("Zeile eins\nZeile zwei");
  });

  it("initializes once — a body prop change does not reset the live document", async () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <SceneEditor body="Erst." onChange={onChange} label="Prosa" />,
    );
    await screen.findByRole("textbox");
    await waitFor(() => expect(screen.getByRole("textbox").textContent).toBe("Erst."));
    // The cache refetch after a save hands the saved body back; the editor
    // keeps its own live content (the page keys it per scene for a swap).
    rerender(<SceneEditor body="Erst." onChange={onChange} label="Prosa" />);
    expect(screen.getByRole("textbox").textContent).toBe("Erst.");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("a scene switch remounts with the new body — the content swap", async () => {
    const { rerender } = render(
      <SceneEditor key="s1" body="Szene eins." onChange={() => {}} label="Prosa" />,
    );
    await screen.findByRole("textbox");
    await waitFor(() => expect(screen.getByRole("textbox").textContent).toBe("Szene eins."));
    // The page keys the editor by scene id: a new key is a new document.
    rerender(<SceneEditor key="s2" body="Szene zwei." onChange={() => {}} label="Prosa" />);
    await waitFor(() => expect(screen.getByRole("textbox").textContent).toBe("Szene zwei."));
  });
});
