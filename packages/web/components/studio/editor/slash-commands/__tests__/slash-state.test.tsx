/**
 * resolveSlashState tests (CR-AUFG-07-20).
 *
 * Verifies the pure-ish editor→slash-state mapping extracted from the hook
 * (RULE-04 modularization): open on `/`, closed mid-paragraph, and that the
 * slash position + selection flag are reported correctly.
 */

import { act, render, waitFor } from "@testing-library/react";
import Placeholder from "@tiptap/extension-placeholder";
import { useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { resolveSlashState } from "../slash-state";

let editorRef: ReturnType<typeof useEditor>;

function Harness() {
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [StarterKit, Placeholder.configure({ placeholder: "p" })],
    content: "<p></p>",
  });
  editorRef = editor as never;
  return <div data-testid="host">{editor ? "ready" : "loading"}</div>;
}

beforeAll(() => {
  if (typeof document.elementFromPoint !== "function") {
    document.elementFromPoint = vi.fn(() => null);
  }
});

async function boot() {
  render(<Harness />);
  await waitFor(() => expect(editorRef).toBeTruthy());
  return editorRef!;
}

describe("resolveSlashState", () => {
  it("is closed before any slash is typed", async () => {
    const editor = await boot();
    const state = resolveSlashState(editor);
    expect(state.open).toBe(false);
  });

  it("opens with the query when `/` is at paragraph start", async () => {
    const editor = await boot();
    act(() => {
      editor.chain().focus().insertContent("/rew").run();
    });
    const state = resolveSlashState(editor);
    expect(state.open).toBe(true);
    if (state.open) {
      expect(state.query).toBe("rew");
      expect(state.slashPos).toBe(1);
    }
  });

  it("reports a selection when text is selected", async () => {
    const editor = await boot();
    act(() => {
      editor.chain().focus().setContent("<p>hello world</p>").run();
    });
    act(() => {
      editor.chain().setTextSelection({ from: 1, to: 6 }).run();
    });
    const state = resolveSlashState(editor);
    expect(state.hasSelection).toBe(true);
  });

  it("is closed when `/` is typed mid-paragraph", async () => {
    const editor = await boot();
    act(() => {
      editor.chain().focus().insertContent("hello /").run();
    });
    const state = resolveSlashState(editor);
    expect(state.open).toBe(false);
  });
});
