/**
 * EditorView tests — central editor orchestration component.
 *
 * Tests:
 * 1. Renders "select chapter" message when no chapter is active
 * 2. Renders loading state when chapter data is pending
 * 3. Renders editor layout with header bar when chapter is loaded
 * 4. Save button triggers handleSave
 * 5. Cmd+K opens command palette
 * 6. Cmd+S triggers save
 * 7. Metadata panel toggle button is visible
 * 8. Storyboard toggle button is visible
 * 9. Generation panel toggle button is visible
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EditorView } from "@/components/studio/EditorView";
import { chaptersApi } from "@/lib/api/client";

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

// Mock editorStore — provides default state and allows per-test overrides
const mockSetSaveStatus = vi.fn();
const mockToggleSidebar = vi.fn();
const mockToggleFocusMode = vi.fn();
const mockToggleContextPanel = vi.fn();
const mockToggleStoryboard = vi.fn();
const mockSetGenerating = vi.fn();
const mockSetActiveRequestId = vi.fn();
const mockSetGenerationMode = vi.fn();
const mockSetDraftText = vi.fn();
const mockSetSessionActive = vi.fn();
const mockToggleGenerationPanel = vi.fn();
const mockToggleExtractionPanel = vi.fn();
const mockToggleVoiceCheckPanel = vi.fn();
const mockToggleRightPanel = vi.fn();
const mockCloseRightPanel = vi.fn();
const mockOpenRightPanel = vi.fn();
const mockSetEditor = vi.fn();

const navigationMocks = vi.hoisted(() => ({
  pathname: "/novel/novel-1",
  push: vi.fn(),
  replace: vi.fn(),
  searchParams: new URLSearchParams(),
}));

let editorStoreState: Record<string, unknown> = {};

vi.mock("@/lib/stores/editorStore", () => ({
  useEditorStore: vi.fn((selector?: (s: Record<string, unknown>) => unknown) => {
    const state = {
      activeChapterId: "chapter-1",
      activeVolumeId: "volume-1",
      editor: null,
      saveStatus: "idle",
      sidebarOpen: true,
      rightPanel: { active: null, previous: null, requestedBy: null },
      focusMode: false,
      storyboardOpen: false,
      isDragging: false,
      isGenerating: false,
      activeRequestId: null,
      generationMode: null,
      draftText: "",
      sessionActive: false,
      extractionPanelOpen: false,
      toggleRightPanel: mockToggleRightPanel,
      closeRightPanel: mockCloseRightPanel,
      openRightPanel: mockOpenRightPanel,
      setSaveStatus: mockSetSaveStatus,
      toggleSidebar: mockToggleSidebar,
      toggleFocusMode: mockToggleFocusMode,
      toggleContextPanel: mockToggleContextPanel,
      toggleStoryboard: mockToggleStoryboard,
      setGenerating: mockSetGenerating,
      setActiveRequestId: mockSetActiveRequestId,
      setGenerationMode: mockSetGenerationMode,
      setDraftText: mockSetDraftText,
      setSessionActive: mockSetSessionActive,
      toggleGenerationPanel: mockToggleGenerationPanel,
      toggleExtractionPanel: mockToggleExtractionPanel,
      toggleVoiceCheckPanel: mockToggleVoiceCheckPanel,
      setEditor: mockSetEditor,
      ...editorStoreState,
    };
    return selector ? selector(state) : state;
  }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigationMocks.pathname,
  useRouter: () => ({ push: navigationMocks.push, replace: navigationMocks.replace }),
  useSearchParams: () => navigationMocks.searchParams,
}));

// Mock API client
vi.mock("@/lib/api/client", () => ({
  chaptersApi: {
    get: vi.fn().mockResolvedValue({
      id: "chapter-1",
      novel_id: "novel-1",
      volume_id: null,
      title: "Test Chapter",
      content: "<p>Chapter content here.</p>",
      summary: "A test chapter summary",
      position: 0,
      word_count: 1500,
      status: "draft",
      pov_character_id: "",
      timeline_position: "",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-15T10:30:00Z",
    }),
    list: vi.fn().mockResolvedValue([
      {
        id: "chapter-1",
        novel_id: "novel-1",
        title: "Chapter One",
        position: 0,
        word_count: 1500,
        status: "draft",
      },
      {
        id: "chapter-2",
        novel_id: "novel-1",
        title: "Chapter Two",
        position: 1,
        word_count: 2300,
        status: "reviewed",
      },
    ]),
    updateMeta: vi.fn().mockResolvedValue({}),
    updateContent: vi.fn().mockResolvedValue({}),
  },
  volumesApi: {
    getStats: vi.fn().mockResolvedValue({
      word_count: 45000,
      chapter_count: 12,
      word_count_target: 50000,
      completion_percentage: 90,
    }),
  },
}));

// Mock generation API
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

// Mock TipTapEditor — complex dependency, mock to simplify EditorView tests
vi.mock("@/components/studio/TipTapEditor", () => ({
  TipTapEditor: vi.fn(({ onChange }) => (
    <div data-testid="tiptap-editor">
      <textarea
        data-testid="tiptap-editor-content"
        onChange={(e) => onChange(e.target.value)}
        defaultValue="Test content"
      />
    </div>
  )),
}));

// Mock other child components that are complex
vi.mock("@/components/studio/editor/CommandPalette", () => ({
  CommandPalette: vi.fn(({ isOpen, onClose }) =>
    isOpen ? (
      <div data-testid="command-palette">
        <button type="button" data-testid="command-palette-close" onClick={onClose}>
          Close
        </button>
      </div>
    ) : null,
  ),
}));

vi.mock("@/components/studio/editor/GenerationPanel", () => ({
  GenerationPanel: vi.fn(() => <div data-testid="generation-panel">Generation Panel</div>),
}));

vi.mock("@/components/studio/analysis/VoiceCheckPanel", () => ({
  VoiceCheckPanel: vi.fn(({ chapterId, onClose }) => (
    <div data-testid="voice-check-panel">
      VoiceCheckPanel
      <span data-testid="voice-check-panel-chapter">{chapterId}</span>
      <button type="button" data-testid="voice-check-panel-close" onClick={onClose}>
        Close
      </button>
    </div>
  )),
}));

vi.mock("@/components/studio/editor/MetadataSidebar", () => ({
  MetadataSidebar: vi.fn(() => <div data-testid="metadata-sidebar">Metadata</div>),
}));

vi.mock("@/components/studio/editor/SessionPanel", () => ({
  SessionPanel: vi.fn(() => <div data-testid="session-panel">Session</div>),
}));

vi.mock("@/components/studio/editor/GhostTextConfig", () => ({
  GhostTextConfig: vi.fn(() => <div data-testid="ghost-text-config" />),
}));

vi.mock("@/components/studio/writing/WritingGraphStatus", () => ({
  WritingGraphStatus: vi.fn(({ steps }) => (
    <div data-testid="writing-graph-status">
      {steps.map((s: { id: string; status: string }) => s.id).join(", ")}
    </div>
  )),
}));

vi.mock("@/components/studio/planning/StoryboardPanel", () => ({
  StoryboardPanel: vi.fn(() => <div data-testid="storyboard-panel" />),
}));

vi.mock("@/components/studio/extraction/ExtractionPanel", () => ({
  ExtractionPanel: vi.fn(() => <div data-testid="extraction-panel" />),
}));

vi.mock("@/components/studio/generation/NameGeneratorModal", () => ({
  NameGeneratorModal: vi.fn(({ isOpen }) =>
    isOpen ? <div data-testid="name-generator-modal" /> : null,
  ),
}));

vi.mock("@/components/studio/editor/AIAnnotationActions", () => ({
  AIAnnotationActions: vi.fn(() => null),
}));

vi.mock("@/components/studio/BlockControls", () => ({
  BlockControls: vi.fn(() => null),
}));

vi.mock("@/lib/hooks/useMemory", () => ({
  useRecordFeedback: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}));

vi.mock("@/lib/api/suggest", () => ({
  createSseSuggestionFetcher: vi.fn(() => vi.fn()),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("EditorView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset editorStoreState to defaults
    editorStoreState = {};
    navigationMocks.searchParams = new URLSearchParams();
  });

  it("renders 'select chapter' message when no chapter is active", () => {
    editorStoreState = { activeChapterId: null };
    renderWithProviders(<EditorView novelId="novel-1" />);
    expect(screen.getByText("editor.selectChapter")).toBeDefined();
  });

  it("renders loading state when chapter data is pending", () => {
    // activeChapterId is set but query is loading
    editorStoreState = { activeChapterId: "chapter-1" };
    // Override chaptersApi.get to never resolve (simulates loading) — only for this call
    vi.mocked(chaptersApi.get).mockImplementationOnce(() => new Promise(() => {}));
    renderWithProviders(<EditorView novelId="novel-1" />);
    // Loading state shows a pulsing element
    const pulse = document.querySelector(".animate-pulse");
    expect(pulse).not.toBeNull();
  });

  it("renders editor layout with header bar when chapter is loaded", async () => {
    editorStoreState = { activeChapterId: "chapter-1" };
    renderWithProviders(<EditorView novelId="novel-1" />);

    // Wait for chapter data to load
    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Chapter")).toBeDefined();
    });

    // Title input is present
    expect(screen.getByDisplayValue("Test Chapter")).toBeDefined();

    // Save button is present
    expect(screen.getByText("editor.save")).toBeDefined();

    // TipTapEditor mock is rendered
    expect(screen.getByTestId("tiptap-editor")).toBeDefined();

    // Writing graph status is rendered
    expect(screen.getByTestId("writing-graph-status")).toBeDefined();
  });

  it("save button triggers handleSave which calls API", async () => {
    const user = userEvent.setup();
    editorStoreState = { activeChapterId: "chapter-1" };
    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Chapter")).toBeDefined();
    });

    const saveButton = screen.getByText("editor.save");
    await user.click(saveButton);

    // Verify API was called
    await waitFor(() => {
      expect(vi.mocked(chaptersApi.updateContent)).toHaveBeenCalled();
    });
  });

  it("Cmd+K opens command palette", async () => {
    editorStoreState = { activeChapterId: "chapter-1" };
    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Chapter")).toBeDefined();
    });

    // Command palette should not be visible initially
    expect(screen.queryByTestId("command-palette")).toBeNull();

    // Press Cmd+K
    fireEvent.keyDown(window, { metaKey: true, key: "k" });

    await waitFor(() => {
      expect(screen.getByTestId("command-palette")).toBeDefined();
    });
  });

  it("Cmd+S triggers save", async () => {
    editorStoreState = { activeChapterId: "chapter-1" };
    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Chapter")).toBeDefined();
    });

    // Press Cmd+S
    fireEvent.keyDown(window, { metaKey: true, key: "s" });

    await waitFor(() => {
      expect(vi.mocked(chaptersApi.updateContent)).toHaveBeenCalled();
    });
  });

  it("metadata panel toggle button is visible", async () => {
    editorStoreState = { activeChapterId: "chapter-1" };
    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Chapter")).toBeDefined();
    });

    // Context panel toggle button exists (aria-label)
    const toggleButton = screen.getByLabelText("metadataSidebar.toggle");
    expect(toggleButton).toBeDefined();
  });

  it("storyboard toggle button is visible", async () => {
    editorStoreState = { activeChapterId: "chapter-1" };
    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Chapter")).toBeDefined();
    });

    const toggleButton = screen.getByLabelText("storyboard.toggleStoryboard");
    expect(toggleButton).toBeDefined();
  });

  it("generation panel toggle button is visible when editor is available", async () => {
    // When editor is available, the toolbar renders with generation button
    // Provide a minimal editor-like object with chain/isActive stubs
    const mockEditor = {
      chain: () => ({
        focus: () => ({
          toggleBold: () => ({ run: () => {} }),
          toggleItalic: () => ({ run: () => {} }),
          toggleHeading: () => ({ run: () => {} }),
          toggleBlockquote: () => ({ run: () => {} }),
        }),
      }),
      isActive: () => false,
      commands: { insertContent: () => {} },
      getHTML: () => "<p>Test</p>",
    };
    editorStoreState = { activeChapterId: "chapter-1", editor: mockEditor };
    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Chapter")).toBeDefined();
    });

    // The generate button should be visible in the toolbar
    expect(screen.getByText("editor.generate")).toBeDefined();
  });

  it("shows metadata sidebar when metadata is the active right panel", async () => {
    editorStoreState = {
      activeChapterId: "chapter-1",
      rightPanel: { active: "metadata", previous: null, requestedBy: "toolbar" },
    };
    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByTestId("metadata-sidebar")).toBeDefined();
    });
  });

  it("shows session panel when session is active", async () => {
    editorStoreState = {
      activeChapterId: "chapter-1",
      sessionActive: true,
      rightPanel: { active: "session", previous: null, requestedBy: "recovery" },
    };
    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByTestId("session-panel")).toBeDefined();
    });
  });

  it("shows generation panel when generation is the active right panel", async () => {
    editorStoreState = {
      activeChapterId: "chapter-1",
      rightPanel: { active: "generation", previous: null, requestedBy: "toolbar" },
    };
    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByTestId("generation-panel")).toBeDefined();
    });
  });

  it("shows voice-check panel when voice-check is the active right panel", async () => {
    editorStoreState = {
      activeChapterId: "chapter-1",
      rightPanel: { active: "voice_check", previous: null, requestedBy: "toolbar" },
    };
    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByTestId("voice-check-panel")).toBeDefined();
    });
    // The panel receives the active chapter id.
    expect(screen.getByTestId("voice-check-panel-chapter").textContent).toBe("chapter-1");
  });

  it("does not show voice-check panel when no right panel is active", async () => {
    editorStoreState = {
      activeChapterId: "chapter-1",
      rightPanel: { active: null, previous: null, requestedBy: null },
    };
    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Chapter")).toBeDefined();
    });
    expect(screen.queryByTestId("voice-check-panel")).toBeNull();
  });

  it("opens a safe editor right panel from URL state", async () => {
    navigationMocks.searchParams = new URLSearchParams("panel=metadata");
    editorStoreState = { activeChapterId: "chapter-1" };

    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(mockOpenRightPanel).toHaveBeenCalledWith("metadata", "url");
    });
  });

  it("normalizes unsafe session panel URL state out of the URL", async () => {
    navigationMocks.searchParams = new URLSearchParams("panel=session");
    editorStoreState = { activeChapterId: "chapter-1" };

    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(navigationMocks.replace).toHaveBeenCalledWith("/novel/novel-1", { scroll: false });
    });
  });

  it("title input updates on change", async () => {
    const user = userEvent.setup();
    editorStoreState = { activeChapterId: "chapter-1" };
    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByDisplayValue("Test Chapter")).toBeDefined();
    });

    const titleInput = screen.getByDisplayValue("Test Chapter");
    await user.clear(titleInput);
    await user.type(titleInput, "New Chapter Title");

    expect(screen.getByDisplayValue("New Chapter Title")).toBeDefined();
  });
});
