/**
 * useContinueStream tests — payload caps, null-editor safety, stream lifecycle (B08).
 *
 * ExtendRequest caps text_before at 10 000 and text_after at 2 000 chars;
 * the hook previously forwarded the raw paragraph split, which 422s on long
 * paragraphs (same FE-exceeds-BE-cap class as audit B01).
 *
 * The lifecycle tests port the bridge behaviour coverage from the pre-Task-10
 * ContinueButton tests (first-chunk insert vs append, finalize on complete,
 * abort → AbortError swallowed → idle, no double-extend while active) — the
 * bridge (continueStream.ts) is the largest moved unit and must not lose it.
 *
 * @module useContinueStream.test
 */

import { act, renderHook } from "@testing-library/react";
import { Editor } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { beforeEach, describe, expect, it, vi } from "vitest";

const streamExtend = vi.hoisted(() => vi.fn(async (..._args: unknown[]) => {}));
const insertAIContent = vi.hoisted(() => vi.fn());
const appendToPendingMark = vi.hoisted(() => vi.fn());
const finalizePendingMark = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/generation", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/generation")>();
  return { ...original, streamExtend: (...args: unknown[]) => streamExtend(...args) };
});

vi.mock("@/components/studio/editor/extensions/AIAnnotation", () => ({
  insertAIContent: (...args: unknown[]) => insertAIContent(...args),
  appendToPendingMark: (...args: unknown[]) => appendToPendingMark(...args),
  finalizePendingMark: (...args: unknown[]) => finalizePendingMark(...args),
}));

import { useContinueStream } from "../useContinueStream";

function createTestEditor(content: string): Editor {
  const element = document.createElement("div");
  document.body.appendChild(element);
  return new Editor({ element, extensions: [StarterKit], content });
}

/** Callbacks object the bridge hands to streamExtend (call args index 3). */
function streamCallbacks(callIndex = 0): {
  onChunk: (text: string) => void;
  onComplete?: () => void;
  onError?: (error: Error) => void;
} {
  return streamExtend.mock.calls[callIndex][3] as ReturnType<typeof streamCallbacks>;
}

describe("useContinueStream", () => {
  beforeEach(() => {
    streamExtend.mockClear();
    // Restore the default: stream starts but never emits (no callbacks fired).
    streamExtend.mockImplementation(async (..._args: unknown[]) => {});
    insertAIContent.mockClear();
    appendToPendingMark.mockClear();
    finalizePendingMark.mockClear();
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

  it("no-ops handleExtend after the editor is destroyed", async () => {
    const editor = createTestEditor("<p>hi</p>");
    editor.destroy();

    const { result } = renderHook(() =>
      useContinueStream({ editor, chapterId: "chapter-1", novelId: "novel-1" }),
    );

    await act(async () => {
      result.current.handleExtend("medium");
    });

    expect(streamExtend).not.toHaveBeenCalled();
  });

  // -------------------------------------------------------------------------
  // Stream lifecycle (ported bridge-behaviour coverage)
  // -------------------------------------------------------------------------

  it("inserts AI content on first chunk and appends on subsequent chunks", async () => {
    const editor = createTestEditor("<p>base</p>");
    editor.commands.setTextSelection(5);

    streamExtend.mockImplementation(async (...args: unknown[]) => {
      const callbacks = args[3] as { onChunk: (text: string) => void; onComplete?: () => void };
      callbacks.onChunk("first ");
      callbacks.onChunk("second ");
      callbacks.onChunk("third");
      callbacks.onComplete?.();
    });

    const { result } = renderHook(() =>
      useContinueStream({ editor, chapterId: "chapter-1", novelId: "novel-1" }),
    );

    await act(async () => {
      result.current.handleExtend("medium");
    });

    // First chunk → insertAIContent with a fresh extend- local id
    expect(insertAIContent).toHaveBeenCalledTimes(1);
    expect(insertAIContent).toHaveBeenCalledWith(
      editor,
      null,
      "first ",
      expect.stringContaining("extend-"),
      "extend",
    );

    // Subsequent chunks → appendToPendingMark
    expect(appendToPendingMark).toHaveBeenCalledTimes(2);
    expect(appendToPendingMark).toHaveBeenNthCalledWith(1, editor, "second ");
    expect(appendToPendingMark).toHaveBeenNthCalledWith(2, editor, "third");

    // Completion → finalizePendingMark with the full accumulated text
    expect(finalizePendingMark).toHaveBeenCalledTimes(1);
    expect(finalizePendingMark).toHaveBeenCalledWith(editor, "first second third");
    expect(result.current.isStreaming).toBe(false);
    editor.destroy();
  });

  it("aborts the active stream on handleStop; the AbortError is swallowed back to idle", async () => {
    const abortSpy = vi.spyOn(AbortController.prototype, "abort");
    const editor = createTestEditor("<p>base</p>");
    editor.commands.setTextSelection(5);

    // Never settles — mirrors an open SSE stream until the test asserts.
    streamExtend.mockImplementation(async () => new Promise<void>(() => {}));

    const { result } = renderHook(() =>
      useContinueStream({ editor, chapterId: "chapter-1", novelId: "novel-1" }),
    );

    await act(async () => {
      result.current.handleExtend("medium");
    });

    // Drive into the streaming state via the first chunk.
    await act(async () => {
      streamCallbacks().onChunk("partial");
    });
    expect(result.current.isStreaming).toBe(true);

    await act(async () => {
      result.current.handleStop();
    });

    expect(abortSpy).toHaveBeenCalled();
    // AbortError rejection is mapped to null by useAIOperation → idle, not error.
    // (The hook surfaces only isLoading/isStreaming; both false = back to idle —
    // the hook-level equivalent of the old test's "button text reverts" check.)
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.isLoading).toBe(false);

    abortSpy.mockRestore();
    editor.destroy();
  });

  it("does not start a second extend while one is active (never-settling guard)", async () => {
    const editor = createTestEditor("<p>base</p>");
    editor.commands.setTextSelection(5);

    streamExtend.mockImplementation(async () => new Promise<void>(() => {}));

    const { result } = renderHook(() =>
      useContinueStream({ editor, chapterId: "chapter-1", novelId: "novel-1" }),
    );

    await act(async () => {
      result.current.handleExtend("medium");
    });
    await act(async () => {
      streamCallbacks().onChunk("partial");
    });
    expect(result.current.isStreaming).toBe(true);

    // Second extend attempt while streaming must be a no-op.
    await act(async () => {
      result.current.handleExtend("long");
    });

    expect(streamExtend).toHaveBeenCalledTimes(1);
    editor.destroy();
  });
});
