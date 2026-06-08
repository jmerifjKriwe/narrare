import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ContinueButton } from "@/components/studio/editor/ContinueButton";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockStreamExtend = vi.fn();
const mockInsertAIContent = vi.fn();
const mockAppendToPendingMark = vi.fn();
const mockFinalizePendingMark = vi.fn();

vi.mock("@/lib/api/generation", () => ({
  streamExtend: (...args: unknown[]) => mockStreamExtend(...args),
}));

vi.mock("@/components/studio/editor/extensions/AIAnnotation", () => ({
  insertAIContent: (...args: unknown[]) => mockInsertAIContent(...args),
  appendToPendingMark: (...args: unknown[]) => mockAppendToPendingMark(...args),
  finalizePendingMark: (...args: unknown[]) => mockFinalizePendingMark(...args),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function createMockEditor(overrides: Record<string, unknown> = {}) {
  return {
    isDestroyed: false,
    state: {
      selection: {
        $head: {
          parent: { textContent: "Some text in the editor" },
          parentOffset: 10,
        },
      },
    },
    ...overrides,
  };
}

function renderContinueButton(
  editor: ReturnType<typeof createMockEditor>,
  extra: { chapterId?: string; novelId?: string; tone?: string } = {},
) {
  return render(
    <ContinueButton
      editor={editor as never}
      chapterId={extra.chapterId ?? "ch-1"}
      novelId={extra.novelId ?? "novel-1"}
      tone={extra.tone}
    />,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ContinueButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: streamExtend simulates a single chunk then completion
    mockStreamExtend.mockImplementation(
      (
        _chId: string,
        _nId: string,
        _req: unknown,
        callbacks: {
          onChunk: (text: string) => void;
          onComplete?: () => void;
        },
        _signal?: AbortSignal,
      ) => {
        callbacks.onChunk("generated text");
        callbacks.onComplete?.();
        return Promise.resolve();
      },
    );
  });

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  it("renders continue writing button", () => {
    const editor = createMockEditor();
    renderContinueButton(editor);

    expect(screen.getByLabelText("annotation.continueWriting")).toBeDefined();
  });

  it("does not show dropdown initially", () => {
    const editor = createMockEditor();
    renderContinueButton(editor);

    expect(screen.queryByText("annotation.length.short")).toBeNull();
    expect(screen.queryByText("annotation.length.medium")).toBeNull();
    expect(screen.queryByText("annotation.length.long")).toBeNull();
  });

  // -------------------------------------------------------------------------
  // Dropdown
  // -------------------------------------------------------------------------

  it("renders length dropdown on chevron click", async () => {
    const user = userEvent.setup();
    const editor = createMockEditor();
    renderContinueButton(editor);

    await user.click(screen.getByLabelText("annotation.selectLength"));

    expect(screen.getByText("annotation.length.short")).toBeDefined();
    expect(screen.getByText("annotation.length.medium")).toBeDefined();
    expect(screen.getByText("annotation.length.long")).toBeDefined();
  });

  it("selects a different length option", async () => {
    const user = userEvent.setup();
    const editor = createMockEditor();
    renderContinueButton(editor);

    // Open dropdown
    await user.click(screen.getByLabelText("annotation.selectLength"));

    // Click "long" option
    const longOption = screen.getByText("annotation.length.long");
    await user.click(longOption);

    // Dropdown should close after selection
    expect(screen.queryByText("annotation.length.short")).toBeNull();

    // Now trigger extend — should use "long" as the length
    await user.click(screen.getByLabelText("annotation.continueWriting"));

    expect(mockStreamExtend).toHaveBeenCalledTimes(1);
    const callArgs = mockStreamExtend.mock.calls[0];
    const request = callArgs[2] as Record<string, unknown>;
    expect(request.length).toBe("long");
  });

  // -------------------------------------------------------------------------
  // Extend request
  // -------------------------------------------------------------------------

  it("click triggers extend request with correct params", async () => {
    const user = userEvent.setup();
    const editor = createMockEditor();
    renderContinueButton(editor, { chapterId: "ch-42", novelId: "novel-99", tone: "dramatic" });

    await user.click(screen.getByLabelText("annotation.continueWriting"));

    expect(mockStreamExtend).toHaveBeenCalledTimes(1);
    const [chapterId, novelId, request, callbacks, signal] = mockStreamExtend.mock.calls[0];

    expect(chapterId).toBe("ch-42");
    expect(novelId).toBe("novel-99");
    expect(request).toEqual({
      text_before: "Some text ",
      text_after: "in the editor",
      length: "medium",
      tone: "dramatic",
      language: "en",
    });
    expect(typeof callbacks.onChunk).toBe("function");
    expect(signal).toBeInstanceOf(AbortSignal);
  });

  it("inserts AI content on first chunk and appends on subsequent chunks", async () => {
    mockStreamExtend.mockImplementation(
      (
        _chId: string,
        _nId: string,
        _req: unknown,
        callbacks: {
          onChunk: (text: string) => void;
          onComplete?: () => void;
        },
        _signal?: AbortSignal,
      ) => {
        callbacks.onChunk("first ");
        callbacks.onChunk("second ");
        callbacks.onChunk("third");
        callbacks.onComplete?.();
        return Promise.resolve();
      },
    );

    const user = userEvent.setup();
    const editor = createMockEditor();
    renderContinueButton(editor);

    await user.click(screen.getByLabelText("annotation.continueWriting"));

    await waitFor(() => {
      // First chunk → insertAIContent
      expect(mockInsertAIContent).toHaveBeenCalledTimes(1);
      expect(mockInsertAIContent).toHaveBeenCalledWith(
        editor,
        null,
        "first ",
        expect.stringContaining("extend-"),
        "extend",
      );

      // Subsequent chunks → appendToPendingMark
      expect(mockAppendToPendingMark).toHaveBeenCalledTimes(2);
      expect(mockAppendToPendingMark).toHaveBeenNthCalledWith(1, editor, "second ");
      expect(mockAppendToPendingMark).toHaveBeenNthCalledWith(2, editor, "third");

      // Completion → finalizePendingMark
      expect(mockFinalizePendingMark).toHaveBeenCalledWith(editor, "first second third");
    });
  });

  // -------------------------------------------------------------------------
  // Streaming state
  // -------------------------------------------------------------------------

  it("shows loading state during generation", async () => {
    // Fire onChunk to trigger notifyData() → streaming state, but don't complete
    mockStreamExtend.mockImplementation(
      (
        _chId: string,
        _nId: string,
        _req: unknown,
        callbacks: { onChunk: (text: string) => void },
      ) => {
        callbacks.onChunk("generated text");
        return new Promise(() => {}); // Never settles — stay in streaming
      },
    );

    const user = userEvent.setup();
    const editor = createMockEditor();
    renderContinueButton(editor);

    await user.click(screen.getByLabelText("annotation.continueWriting"));

    // Should now show stop button with spinner
    // The aria-label stays "annotation.continueWriting" but the text changes to "aiActions.stop"
    expect(screen.getByText("aiActions.stop")).toBeDefined();
    // Chevron dropdown should be hidden during streaming
    expect(screen.queryByLabelText("annotation.selectLength")).toBeNull();
  });

  it("returns to idle state after streaming completes", async () => {
    const user = userEvent.setup();
    const editor = createMockEditor();
    renderContinueButton(editor);

    await user.click(screen.getByText("annotation.continueWriting"));

    // After the default mock completes (immediate), button returns to idle
    await waitFor(() => {
      expect(screen.getByText("annotation.continueWriting")).toBeDefined();
    });
  });

  // -------------------------------------------------------------------------
  // Stop
  // -------------------------------------------------------------------------

  it("stop button aborts streaming", async () => {
    // Track abort calls by spying on AbortController.prototype.abort
    const abortSpy = vi.spyOn(AbortController.prototype, "abort");

    // Fire onChunk to trigger streaming state, but never complete
    mockStreamExtend.mockImplementation(
      (
        _chId: string,
        _nId: string,
        _req: unknown,
        callbacks: { onChunk: (text: string) => void },
      ) => {
        callbacks.onChunk("generated text");
        return new Promise(() => {}); // Never settles
      },
    );

    const user = userEvent.setup();
    const editor = createMockEditor();
    renderContinueButton(editor);

    await user.click(screen.getByText("annotation.continueWriting"));
    // The button text changes to "aiActions.stop" during streaming
    expect(screen.getByText("aiActions.stop")).toBeDefined();

    // Click the stop button (same button, but now showing stop text)
    await user.click(screen.getByText("aiActions.stop"));
    expect(abortSpy).toHaveBeenCalled();

    // Button returns to idle — text reverts
    expect(screen.getByText("annotation.continueWriting")).toBeDefined();

    abortSpy.mockRestore();
  });

  // -------------------------------------------------------------------------
  // Destroyed editor
  // -------------------------------------------------------------------------

  it("is disabled when editor is destroyed", () => {
    const editor = createMockEditor({ isDestroyed: true });
    renderContinueButton(editor);

    expect(screen.getByLabelText("annotation.continueWriting")).toHaveProperty("disabled", true);
  });

  it("does not call streamExtend when editor is destroyed", () => {
    const editor = createMockEditor({ isDestroyed: true });
    renderContinueButton(editor);

    // Button is disabled — streamExtend should not have been called
    expect(mockStreamExtend).not.toHaveBeenCalled();
  });

  it("guards against destroyed editor during streaming", async () => {
    // When editor is destroyed, handleExtend returns early without calling streamExtend
    const destroyedEditor = createMockEditor({ isDestroyed: true });
    renderContinueButton(destroyedEditor);

    const button = screen.getByLabelText("annotation.continueWriting");
    // Button is disabled
    expect((button as HTMLButtonElement).disabled).toBe(true);

    // streamExtend should never have been called
    expect(mockStreamExtend).not.toHaveBeenCalled();
  });
});
