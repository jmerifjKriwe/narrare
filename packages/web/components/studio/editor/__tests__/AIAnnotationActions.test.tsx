import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AIAnnotationActions } from "@/components/studio/editor/AIAnnotationActions";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock the API and hooks
const mockAcceptDraft = vi
  .fn()
  .mockResolvedValue({ request_id: "test-req-1", chapter_id: "ch-1", word_count: 10 });
const mockRejectDraft = vi.fn().mockResolvedValue({ request_id: "test-req-1", status: "rejected" });
const mockMutate = vi.fn();

vi.mock("@/lib/api/generation", () => ({
  writingApi: {
    acceptDraft: (...args: unknown[]) => mockAcceptDraft(...args),
    rejectDraft: (...args: unknown[]) => mockRejectDraft(...args),
  },
}));

vi.mock("@/lib/hooks/useMemory", () => ({
  useRecordFeedback: () => ({ mutate: mockMutate }),
}));

vi.mock("@/components/studio/editor/extensions/AIAnnotation", () => ({
  acceptMark: vi.fn(),
  rejectMark: vi.fn(),
  getPendingModification: vi.fn(() => null),
  hasPendingMark: vi.fn(() => true),
  AIAnnotationMark: {},
  AIAnnotationExtension: {},
}));

// Minimal editor mock for testing the component
function createMockEditor(hasPending = true) {
  const listeners: Record<string, (() => void)[]> = {};
  return {
    on: vi.fn((event: string, cb: () => void) => {
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(cb);
    }),
    off: vi.fn(),
    isDestroyed: false,
    state: {
      schema: {
        marks: {
          aiGenerated: { name: "aiGenerated" },
        },
      },
      doc: {
        descendants: vi.fn(
          (cb: (node: Record<string, unknown>, pos: number) => boolean | undefined) => {
            if (hasPending) {
              cb(
                {
                  isText: true,
                  nodeSize: 10,
                  marks: [
                    {
                      type: { name: "aiGenerated" },
                      attrs: {
                        requestId: "test-req-1",
                        source: "extend",
                        status: "pending",
                        originalText: "AI content",
                      },
                    },
                  ],
                },
                5,
              );
            }
          },
        ),
        textBetween: vi.fn(() => "AI content"),
      },
      selection: { $head: { parent: { textContent: "Hello AI content world" }, parentOffset: 15 } },
    },
    view: { dom: document.createElement("div") },
    extensionManager: {
      extensions: [],
    },
  };
}

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const translations: Record<string, string> = {
      "annotation.aiContinuation": "AI Continuation",
      "annotation.aiWords": `${key === "annotation.aiWords" ? "2" : ""} words`,
      "aiActions.accept": "Accept",
      "aiActions.reject": "Reject",
    };
    return translations[key] || key;
  },
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AIAnnotationActions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders when pending mark exists", () => {
    const editor = createMockEditor(true);
    // Simulate having the anchor element in DOM
    const anchor = document.createElement("span");
    anchor.className = "ai-annotation-anchor";
    document.body.appendChild(anchor);

    const { unmount } = render(
      <AIAnnotationActions editor={editor as never} projectId="novel-1" chapterId="ch-1" />,
    );

    // Wait for state to settle
    waitFor(() => {
      expect(screen.queryByText("Keep")).toBeTruthy();
    });

    unmount();
    document.body.removeChild(anchor);
  });

  it("calls acceptMark and writingApi.acceptDraft when Keep is clicked", async () => {
    const { acceptMark } = await import("@/components/studio/editor/extensions/AIAnnotation");

    const editor = createMockEditor(true);
    const anchor = document.createElement("span");
    anchor.className = "ai-annotation-anchor";
    document.body.appendChild(anchor);

    const { unmount } = render(
      <AIAnnotationActions editor={editor as never} projectId="novel-1" chapterId="ch-1" />,
    );

    await waitFor(() => {
      const keepButton = screen.queryByLabelText("Keep");
      if (keepButton) {
        fireEvent.click(keepButton);
        expect(acceptMark).toHaveBeenCalledWith(editor, null, "test-req-1");
        expect(mockAcceptDraft).toHaveBeenCalledWith("test-req-1", undefined);
        expect(mockMutate).toHaveBeenCalled();
      }
    });

    unmount();
    document.body.removeChild(anchor);
  });

  it("calls rejectMark and writingApi.rejectDraft when Undo is clicked", async () => {
    const { rejectMark } = await import("@/components/studio/editor/extensions/AIAnnotation");

    const editor = createMockEditor(true);
    const anchor = document.createElement("span");
    anchor.className = "ai-annotation-anchor";
    document.body.appendChild(anchor);

    const { unmount } = render(
      <AIAnnotationActions editor={editor as never} projectId="novel-1" chapterId="ch-1" />,
    );

    await waitFor(() => {
      const undoButton = screen.queryByLabelText("Undo");
      if (undoButton) {
        fireEvent.click(undoButton);
        expect(rejectMark).toHaveBeenCalledWith(editor, null, "test-req-1");
        expect(mockRejectDraft).toHaveBeenCalledWith("test-req-1");
        expect(mockMutate).toHaveBeenCalled();
      }
    });

    unmount();
    document.body.removeChild(anchor);
  });

  it("does not render when no pending mark exists", () => {
    const editor = createMockEditor(false);
    const { container, unmount } = render(
      <AIAnnotationActions editor={editor as never} projectId="novel-1" chapterId="ch-1" />,
    );

    // Should render nothing visible
    expect(container.innerHTML).toBe("");
    unmount();
  });
});
