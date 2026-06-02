/**
 * ContinueButton tests
 *
 * NOTE: Comprehensive tests for ContinueButton already exist at:
 *   packages/web/components/studio/editor/__tests__/ContinueButton.test.tsx
 *
 * This file provides supplementary tests covering additional edge cases
 * as specified by the test task requirements.
 *
 * The existing test file covers:
 * - Renders continue writing button
 * - Dropdown opens/closes on click
 * - Length options render correctly (short, medium, long)
 * - Shows stop button during streaming state
 * - Button disabled when editor is destroyed
 * - Click triggers extend with correct length
 * - Streaming content insertion (first chunk + subsequent chunks)
 * - Stop button aborts streaming
 *
 * This file adds:
 * - Default length is "medium"
 * - Dropdown closes on outside click
 * - No action when phase is streaming and extend is attempted
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ContinueButton } from "./ContinueButton";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockStreamExtend = vi.fn();

vi.mock("@/lib/api/generation", () => ({
  streamExtend: (...args: unknown[]) => mockStreamExtend(...args),
}));

vi.mock("@/components/studio/editor/extensions/AIAnnotation", () => ({
  insertAIContent: vi.fn(),
  appendToPendingMark: vi.fn(),
  finalizePendingMark: vi.fn(),
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
          parent: { textContent: "Hello world" },
          parentOffset: 5,
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

describe("ContinueButton (supplementary)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStreamExtend.mockImplementation(
      (
        _chId: string,
        _nId: string,
        _req: unknown,
        callbacks: { onChunk: (text: string) => void; onComplete?: () => void },
      ) => {
        callbacks.onChunk("extended text");
        callbacks.onComplete?.();
      },
    );
  });

  // -------------------------------------------------------------------------
  // Default length
  // -------------------------------------------------------------------------

  it("defaults to medium length", async () => {
    const user = userEvent.setup();
    const editor = createMockEditor();
    renderContinueButton(editor);

    // Click the main button (not dropdown)
    await user.click(screen.getByLabelText("annotation.continueWriting"));

    // Verify the request was sent with length "medium"
    expect(mockStreamExtend).toHaveBeenCalledTimes(1);
    const request = mockStreamExtend.mock.calls[0][2] as Record<string, unknown>;
    expect(request.length).toBe("medium");
  });

  // -------------------------------------------------------------------------
  // Dropdown close on outside click
  // -------------------------------------------------------------------------

  it("closes dropdown when clicking outside", async () => {
    const user = userEvent.setup();
    const editor = createMockEditor();
    renderContinueButton(editor);

    // Open dropdown
    await user.click(screen.getByLabelText("annotation.selectLength"));
    expect(screen.getByText("annotation.length.short")).toBeInTheDocument();

    // Click outside the dropdown (on the body)
    await user.click(document.body);

    // Dropdown should close
    await waitFor(() => {
      expect(screen.queryByText("annotation.length.short")).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Dropdown closes after selecting length
  // -------------------------------------------------------------------------

  it("closes dropdown after selecting a length option", async () => {
    const user = userEvent.setup();
    const editor = createMockEditor();
    renderContinueButton(editor);

    // Open dropdown
    await user.click(screen.getByLabelText("annotation.selectLength"));

    // Select "long"
    await user.click(screen.getByText("annotation.length.long"));

    // Dropdown closes
    expect(screen.queryByText("annotation.length.short")).not.toBeInTheDocument();

    // Trigger extend — should use "long"
    await user.click(screen.getByLabelText("annotation.continueWriting"));
    const request = mockStreamExtend.mock.calls[0][2] as Record<string, unknown>;
    expect(request.length).toBe("long");
  });

  // -------------------------------------------------------------------------
  // No duplicate extend calls during streaming
  // -------------------------------------------------------------------------

  it("does not trigger another extend while already streaming", async () => {
    // Make the first streamExtend hang
    mockStreamExtend.mockReturnValue(new Promise(() => {}));

    const user = userEvent.setup();
    const editor = createMockEditor();
    renderContinueButton(editor);

    // Click to start streaming
    await user.click(screen.getByText("annotation.continueWriting"));

    // Now the button shows "stop" — clicking it should stop, not extend
    expect(screen.getByText("aiActions.stop")).toBeInTheDocument();

    // Click the stop button
    await user.click(screen.getByText("aiActions.stop"));

    // streamExtend should have been called only once
    expect(mockStreamExtend).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // Tone parameter passed through
  // -------------------------------------------------------------------------

  it("passes tone parameter to streamExtend", async () => {
    const user = userEvent.setup();
    const editor = createMockEditor();
    renderContinueButton(editor, { tone: "whimsical" });

    await user.click(screen.getByLabelText("annotation.continueWriting"));

    const request = mockStreamExtend.mock.calls[0][2] as Record<string, unknown>;
    expect(request.tone).toBe("whimsical");
  });

  // -------------------------------------------------------------------------
  // Text extraction from editor
  // -------------------------------------------------------------------------

  it("extracts text_before and text_after from editor selection", async () => {
    const user = userEvent.setup();
    const editor = createMockEditor();
    renderContinueButton(editor);

    await user.click(screen.getByLabelText("annotation.continueWriting"));

    const request = mockStreamExtend.mock.calls[0][2] as Record<string, unknown>;
    // textBefore = "Hello".slice(0, 5) = "Hello"
    // textAfter = "Hello world".slice(5) = " world"
    expect(request.text_before).toBe("Hello");
    expect(request.text_after).toBe(" world");
  });
});
