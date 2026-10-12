/**
 * useContinueStream tests — payload caps + null-editor safety (B08).
 *
 * ExtendRequest caps text_before at 10 000 and text_after at 2 000 chars;
 * the hook previously forwarded the raw paragraph split, which 422s on long
 * paragraphs (same FE-exceeds-BE-cap class as audit B01).
 *
 * @module useContinueStream.test
 */

import { act, renderHook } from "@testing-library/react";
import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { beforeEach, describe, expect, it, vi } from "vitest";

const streamExtend = vi.hoisted(() => vi.fn(async (..._args: unknown[]) => {}));

vi.mock("@/lib/api/generation", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/generation")>();
  return { ...original, streamExtend: (...args: unknown[]) => streamExtend(...args) };
});

import { useContinueStream } from "../useContinueStream";

function createTestEditor(content: string): Editor {
  const element = document.createElement("div");
  document.body.appendChild(element);
  return new Editor({ element, extensions: [StarterKit], content });
}

describe("useContinueStream", () => {
  beforeEach(() => {
    streamExtend.mockClear();
  });

  it("clamps text_before to the 10 000-char backend cap", async () => {
    const editor = createTestEditor(`<p>${"w".repeat(12_000)}</p>`);
    editor.commands.focus("end");

    const { result } = renderHook(() =>
      useContinueStream({ editor, chapterId: "chapter-1", novelId: "novel-1" }),
    );

    // useAIOperation.start() defers invokeExecute via queueMicrotask — flush.
    await act(async () => {
      result.current.handleExtend("short");
    });

    expect(streamExtend).toHaveBeenCalledOnce();
    const body = streamExtend.mock.calls[0][2] as { text_before: string; length: string };
    expect(body.text_before.length).toBe(10_000);
    expect(body.length).toBe("short");
    editor.destroy();
  });

  it("clamps text_after to the 2 000-char backend cap", async () => {
    // Caret at the START of a long paragraph: everything after is text_after.
    const editor = createTestEditor(`<p>${"w".repeat(3_000)}</p>`);
    editor.commands.setTextSelection(1);

    const { result } = renderHook(() =>
      useContinueStream({ editor, chapterId: "chapter-1", novelId: "novel-1" }),
    );

    await act(async () => {
      result.current.handleExtend("medium");
    });

    const body = streamExtend.mock.calls[0][2] as { text_after: string | null };
    expect((body.text_after ?? "").length).toBe(2_000);
    editor.destroy();
  });

  it("is a no-op while the editor is null (Task 11 owner pattern)", async () => {
    const { result } = renderHook(() =>
      useContinueStream({ editor: null, chapterId: "chapter-1", novelId: "novel-1" }),
    );

    await act(async () => {
      result.current.handleExtend("medium");
    });

    expect(streamExtend).not.toHaveBeenCalled();
  });
});
