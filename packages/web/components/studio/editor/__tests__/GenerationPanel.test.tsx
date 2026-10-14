import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, type Mock, vi } from "vitest";
import { GenerationPanel } from "@/components/studio/editor/GenerationPanel";
import { ApiError } from "@/lib/api/core";

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

const mockStartGeneration = vi.fn();

vi.mock("@/lib/api/generation", () => ({
  writingApi: {
    startGeneration: (...args: unknown[]) => mockStartGeneration(...args),
    stopGeneration: vi.fn(),
    acceptDraft: vi.fn().mockResolvedValue({
      request_id: "gen-test-id",
      chapter_id: "chapter-1",
      word_count: 500,
    }),
    rejectDraft: vi.fn().mockResolvedValue({
      request_id: "gen-test-id",
      status: "rejected",
    }),
  },
  streamGeneration: vi.fn(),
}));

vi.mock("@/lib/hooks/useMemory", () => ({
  useMemoryStatus: () => ({
    eventCount: 0,
    confidence: 0,
    hasProfile: false,
    data: null,
  }),
  useRecordFeedback: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}));

vi.mock("@/components/studio/learning/LearningStatus", () => ({
  LearningStatus: () => <span data-testid="learning-status" />,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  novelId: "novel-1",
  chapterId: "chapter-1",
  chapterContent: "",
  onDraftAccepted: vi.fn(),
  onClose: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("GenerationPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStartGeneration.mockResolvedValue({
      request_id: "gen-test-id",
      status: "pending",
      mode: "full_draft",
    });
  });

  it("renders panel title", () => {
    renderWithProviders(<GenerationPanel {...defaultProps} />);
    expect(screen.getByText("generationPanel.title")).toBeDefined();
  });

  it("does not render ContextInspector before generation starts", () => {
    renderWithProviders(<GenerationPanel {...defaultProps} />);
    // ContextInspector should not be visible in config phase
    expect(screen.queryByText("contextInspector.toggle")).toBeNull();
  });

  it("renders ContextInspector after generation with context metadata", async () => {
    const { streamGeneration } = await import("@/lib/api/generation");
    const streamMock = streamGeneration as Mock;

    streamMock.mockImplementation(
      async (
        _requestId: string,
        onChunk: (chunk: { text: string; is_final?: boolean }) => void,
        onComplete?: () => void,
        _onError?: (error: Error) => void,
        _signal?: AbortSignal,
        _onUsage?: (usage: unknown) => void,
        onContextMeta?: (meta: { type: string; [key: string]: unknown }) => void,
      ) => {
        onContextMeta?.({
          type: "context_meta",
          kb_characters_count: 3,
          kb_locations_count: 1,
          kb_factions_count: 0,
          kb_suggested_count: 0,
          kb_pinned_count: 0,
          recent_chapter_count: 2,
          character_names: ["Anna", "Johann", "Waldgeist"],
          location_names: ["Försterhaus"],
          faction_names: [],
          is_first_chapter: false,
          has_user_preferences: true,
          tone: "dramatic",
          total_budget_tokens: 8000,
        });
        // is_final: production streams end with a final chunk; without it the
        // stream counts as dead (M06 guard) and never completes.
        onChunk({ text: "Once upon a time...", is_final: true });
        onComplete?.();
      },
    );

    renderWithProviders(<GenerationPanel {...defaultProps} />);

    // Start generation
    fireEvent.click(screen.getByText("generationPanel.generate"));

    // Wait for the streaming to start and context meta to be rendered
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "contextInspector.toggle" })).toBeDefined();
    });
  });

  it("renders the localized validation message for 422 MISSING_INPUT (M06)", async () => {
    // next-intl is mocked globally to echo keys (setupTests.ts), so the
    // localized rendering assertion is on the KEY being passed to t().
    mockStartGeneration.mockRejectedValue(
      new ApiError("At least one of prompt, outline, or auto_continue", 422, "MISSING_INPUT"),
    );
    renderWithProviders(
      <GenerationPanel
        novelId="novel-1"
        chapterId="chapter-1"
        chapterContent=""
        onDraftAccepted={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "generationPanel.generate" }));

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toBe("generationPanel.validationMissingInput"),
    );
    // M06 pin: the German connection-lost fallback must NOT be the rendered text.
    expect(screen.getByRole("alert").textContent).not.toContain("Verbindung");
  });
});
