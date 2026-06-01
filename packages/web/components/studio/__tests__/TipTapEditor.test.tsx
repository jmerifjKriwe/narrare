/**
 * TipTapEditor tests — TipTap v3 editor with custom extensions.
 *
 * Tests:
 * 1. Editor initializes and renders content
 * 2. Content changes propagate via onChange callback
 * 3. Editor instance is synced to editorStore
 * 4. Custom extensions are registered (NarrareDocument, SceneBreak, DialogueMark)
 * 5. Empty content handling
 * 6. BubbleMenu shows on text selection
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { TipTapEditor } from "@/components/studio/TipTapEditor";

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Track calls to setEditor so tests can assert on them.
// We use an array reference because vi.mock is hoisted and cannot reference
// top-level let/const declared below it.
const setEditorCalls: unknown[] = [];

vi.mock("@/lib/stores/editorStore", () => {
  const getState = vi.fn(() => ({
    isDragging: false,
    setEditor: (editor: unknown) => {
      setEditorCalls.push(editor);
    },
  }));
  return {
    useEditorStore: Object.assign(
      vi.fn((selector?: (s: Record<string, unknown>) => unknown) => {
        const state = {
          isDragging: false,
          setEditor: (editor: unknown) => {
            setEditorCalls.push(editor);
          },
        };
        return selector ? selector(state) : state;
      }),
      { getState },
    ),
  };
});

vi.mock("@/lib/api/generation", () => ({
  writingApi: {
    startGeneration: vi.fn(),
    acceptDraft: vi.fn(),
    rejectDraft: vi.fn(),
    stopGeneration: vi.fn(),
  },
  streamGeneration: vi.fn(),
  streamRewrite: vi.fn(),
}));

vi.mock("@/lib/api/suggest", () => ({
  createSseSuggestionFetcher: vi.fn(() => vi.fn()),
}));

vi.mock("@/lib/hooks/useMemory", () => ({
  useRecordFeedback: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}));

vi.mock("@/components/studio/BlockControls", () => ({
  BlockControls: vi.fn(() => null),
}));

vi.mock("@/components/studio/editor/AIAnnotationActions", () => ({
  AIAnnotationActions: vi.fn(() => null),
}));

vi.mock("@/components/studio/editor/InlineDiff", () => ({
  InlineDiff: vi.fn(({ original, alternative }) => (
    <div data-testid="inline-diff">
      <span>{original}</span>
      <span>{alternative}</span>
    </div>
  )),
}));

vi.mock("@/components/studio/editor/RewriteModeSelector", () => ({
  RewriteModeSelector: vi.fn(() => <div data-testid="rewrite-mode-selector" />),
}));

// ---------------------------------------------------------------------------
// JSDOM polyfills
// ---------------------------------------------------------------------------

beforeAll(() => {
  // TipTap v3 placeholder viewport tracking calls document.elementFromPoint
  // during editor mount. JSDOM does not implement this DOM API, so we
  // polyfill it with the semantically correct return value (null = no element
  // at the given coordinates, which is always true in a headless environment).
  if (typeof document.elementFromPoint !== "function") {
    document.elementFromPoint = vi.fn(() => null);
  }
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TipTapEditor", () => {
  const mockOnChange = vi.fn();
  const mockOnAutosave = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    vi.clearAllMocks();
    setEditorCalls.length = 0;
  });

  it("renders editor with provided content", () => {
    const content = "<p>Hello world</p>";
    renderWithProviders(
      <TipTapEditor
        content={content}
        onChange={mockOnChange}
        onAutosave={mockOnAutosave}
        chapterId="chapter-1"
        novelId="novel-1"
      />,
    );

    // TipTap renders content inside .tiptap element
    const editorElement = document.querySelector(".tiptap");
    expect(editorElement).not.toBeNull();
    expect(editorElement?.textContent).toContain("Hello world");
  });

  it("wires onChange to the TipTap editor onUpdate callback", async () => {
    const content = "<p>Initial content</p>";
    renderWithProviders(
      <TipTapEditor
        content={content}
        onChange={mockOnChange}
        onAutosave={mockOnAutosave}
        chapterId="chapter-1"
        novelId="novel-1"
      />,
    );

    // Wait for editor to initialize and verify it was created
    await waitFor(() => {
      expect(setEditorCalls.length).toBeGreaterThan(0);
    });

    // The editor was initialized with onUpdate handler that calls onChange
    // We can verify the editor was configured by checking the editor instance
    const editor = setEditorCalls[0] as { options: { onUpdate?: (...args: unknown[]) => void } };
    expect(editor.options.onUpdate).toBeDefined();

    // Simulate what TipTap does: call onUpdate with the editor instance
    // This verifies the onChange wiring works correctly
    const updateHandler = editor.options.onUpdate;
    const mockEditorRef = {
      getHTML: () => "<p>Updated content</p>",
    };
    updateHandler?.call(editor as never, { editor: mockEditorRef, transaction: {} } as never);

    expect(mockOnChange).toHaveBeenCalledWith("<p>Updated content</p>");
  });

  it("syncs editor instance to editorStore via setEditor", async () => {
    const content = "<p>Test content</p>";
    renderWithProviders(
      <TipTapEditor
        content={content}
        onChange={mockOnChange}
        onAutosave={mockOnAutosave}
        chapterId="chapter-1"
        novelId="novel-1"
      />,
    );

    // Wait for editor to initialize and sync to store
    await waitFor(() => {
      expect(setEditorCalls.length).toBeGreaterThan(0);
    });

    // The setEditor should have been called with a TipTap Editor instance
    const editorArg = setEditorCalls[0];
    expect(editorArg).not.toBeNull();
    // TipTap Editor has getHTML method
    expect(typeof (editorArg as { getHTML: () => string }).getHTML).toBe("function");
  });

  it("registers custom extensions (NarrareDocument, SceneBreak, DialogueMark)", async () => {
    const content = "<p>Test content</p>";
    renderWithProviders(
      <TipTapEditor
        content={content}
        onChange={mockOnChange}
        onAutosave={mockOnAutosave}
        chapterId="chapter-1"
        novelId="novel-1"
      />,
    );

    // Wait for editor to initialize
    await waitFor(() => {
      expect(setEditorCalls.length).toBeGreaterThan(0);
    });

    // Get the editor instance and check extensions
    const editor = setEditorCalls[0] as {
      extensionManager: { extensions: Array<{ name: string }> };
    };
    const extensionNames = editor.extensionManager.extensions.map((ext) => ext.name);

    // Verify custom extensions are registered
    // NarrareDocument replaces the default "doc" node
    expect(extensionNames).toContain("doc");
    expect(extensionNames).toContain("sceneBreak");
    // DialogueMark registers as "dialogue"
    expect(extensionNames).toContain("dialogue");
    expect(extensionNames).toContain("autosave");
  });

  it("handles empty content", () => {
    const content = "";
    renderWithProviders(
      <TipTapEditor
        content={content}
        onChange={mockOnChange}
        onAutosave={mockOnAutosave}
        chapterId="chapter-1"
        novelId="novel-1"
      />,
    );

    // Editor should still render (with placeholder)
    const editorElement = document.querySelector(".tiptap");
    expect(editorElement).not.toBeNull();
  });

  it("renders placeholder text when content is empty", () => {
    const content = "";
    renderWithProviders(
      <TipTapEditor
        content={content}
        onChange={mockOnChange}
        onAutosave={mockOnAutosave}
        chapterId="chapter-1"
        novelId="novel-1"
      />,
    );

    // Placeholder is rendered via TipTap's Placeholder extension
    // The placeholder element has a data-placeholder attribute or .is-empty class
    const placeholder = document.querySelector("[data-placeholder]");
    expect(placeholder).not.toBeNull();
  });

  it("updates content when prop changes", async () => {
    const { rerender } = renderWithProviders(
      <TipTapEditor
        content="<p>First content</p>"
        onChange={mockOnChange}
        onAutosave={mockOnAutosave}
        chapterId="chapter-1"
        novelId="novel-1"
      />,
    );

    // Wait for initial render
    await waitFor(() => {
      const editorElement = document.querySelector(".tiptap");
      expect(editorElement).not.toBeNull();
    });

    // Rerender with new content
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <TipTapEditor
          content="<p>Updated content</p>"
          onChange={mockOnChange}
          onAutosave={mockOnAutosave}
          chapterId="chapter-1"
          novelId="novel-1"
        />
      </QueryClientProvider>,
    );

    // Content should be updated
    await waitFor(() => {
      const editorElement = document.querySelector(".tiptap");
      expect(editorElement?.textContent).toContain("Updated content");
    });
  });

  it("renders without novelId (disables feedback)", () => {
    const content = "<p>Test content</p>";
    renderWithProviders(
      <TipTapEditor
        content={content}
        onChange={mockOnChange}
        onAutosave={mockOnAutosave}
        chapterId="chapter-1"
      />,
    );

    // Editor should still render
    const editorElement = document.querySelector(".tiptap");
    expect(editorElement).not.toBeNull();
  });

  it("renders without chapterId (disables suggestions)", () => {
    const content = "<p>Test content</p>";
    renderWithProviders(
      <TipTapEditor
        content={content}
        onChange={mockOnChange}
        onAutosave={mockOnAutosave}
        novelId="novel-1"
      />,
    );

    // Editor should still render
    const editorElement = document.querySelector(".tiptap");
    expect(editorElement).not.toBeNull();
  });
});
