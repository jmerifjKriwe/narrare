/**
 * GenerationPanel tests — panel lifecycle, M06 stream/accept contract, and the
 * generation flow (config → streaming → review → rating/feedback).
 *
 * The flow tests (config panel, streaming text, RatingPrompt, feedback
 * enrichment, LearningStatus) were ported from the deleted stale orphan
 * `packages/web/__tests__/GenerationPanel.test.tsx` and adapted to the M06
 * contract: streams end with an `is_final: true` chunk and accept sends the
 * draft text as the request body.
 */

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

const mockRecordFeedbackMutate = vi.fn();
vi.mock("@/lib/hooks/useMemory", () => ({
  useMemoryStatus: () => ({
    eventCount: 10,
    confidence: 0.5,
    hasProfile: true,
    data: { event_count: 10, confidence: 0.5 },
  }),
  useRecordFeedback: () => ({
    mutate: mockRecordFeedbackMutate,
    isPending: false,
  }),
}));

vi.mock("@/components/studio/learning/LearningStatus", () => ({
  LearningStatus: ({ eventCount }: { eventCount: number; compact?: boolean }) => (
    <span data-testid="learning-status">{eventCount}</span>
  ),
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

  // -------------------------------------------------------------------------
  // Ported from the deleted stale orphan (packages/web/__tests__/
  // GenerationPanel.test.tsx), adapted to the M06 contract: every stream ends
  // with an `is_final: true` chunk (without it the M06 guard routes to the
  // error phase and review is never reached), and accept sends the draft text
  // as the request body.
  // -------------------------------------------------------------------------

  /** Streams the given chunk texts, marking the last one `is_final` (M06 guard). */
  async function mockStreamText(...texts: string[]) {
    const { streamGeneration } = await import("@/lib/api/generation");
    const streamMock = streamGeneration as unknown as Mock;
    streamMock.mockImplementation(
      async (
        _requestId: string,
        onChunk: (chunk: { text: string; is_final?: boolean }) => void,
        onComplete?: () => void,
      ) => {
        texts.forEach((text, i) => {
          onChunk({ text, is_final: i === texts.length - 1 });
        });
        onComplete?.();
      },
    );
  }

  it("renders generation config panel with trigger button", () => {
    renderWithProviders(<GenerationPanel {...defaultProps} />);
    // The generate button is present in config phase
    expect(screen.getByText("generationPanel.generate")).toBeDefined();
  });

  it("shows config panel in initial phase", () => {
    renderWithProviders(<GenerationPanel {...defaultProps} />);
    // Mode tabs are visible
    expect(screen.getByText("generationPanel.modeFullDraft")).toBeDefined();
    expect(screen.getByText("generationPanel.modeSceneByScene")).toBeDefined();
    // Close button is visible
    expect(screen.getByRole("button", { name: "generationPanel.close" })).toBeDefined();
  });

  it("displays streaming response text after generation starts", async () => {
    await mockStreamText("Once upon a time", " in a land far away.");

    renderWithProviders(<GenerationPanel {...defaultProps} />);

    // Click generate
    fireEvent.click(screen.getByText("generationPanel.generate"));

    await waitFor(() => {
      expect(screen.getByText(/Once upon a time/)).toBeDefined();
    });

    await waitFor(() => {
      expect(screen.getByText(/in a land far away/)).toBeDefined();
    });
  });

  it("shows RatingPrompt after accept", async () => {
    await mockStreamText("Generated draft text.");

    renderWithProviders(<GenerationPanel {...defaultProps} />);

    // Start generation
    fireEvent.click(screen.getByText("generationPanel.generate"));

    // Wait for review phase
    await waitFor(() => {
      expect(screen.getByText("aiActions.accept")).toBeDefined();
    });

    // Accept the draft (sends draftText as the accept body — M06 contract)
    fireEvent.click(screen.getByText("aiActions.accept"));

    // RatingPrompt should appear
    await waitFor(() => {
      expect(screen.getByText("aiActions.rating")).toBeDefined();
    });
  });

  it("shows RatingPrompt with reject reason textarea after reject", async () => {
    await mockStreamText("Bad draft text.");

    renderWithProviders(<GenerationPanel {...defaultProps} />);

    // Start generation
    fireEvent.click(screen.getByText("generationPanel.generate"));

    await waitFor(() => {
      expect(screen.getByText("aiActions.reject")).toBeDefined();
    });

    // Reject the draft
    fireEvent.click(screen.getByText("aiActions.reject"));

    // RatingPrompt with reject reason textarea should appear
    await waitFor(() => {
      expect(screen.getByText("aiActions.rating")).toBeDefined();
      expect(screen.getByPlaceholderText("aiActions.rejectReason")).toBeDefined();
    });
  });

  // Orphan name was "sends modify feedback when text was edited before accept",
  // but it never edited the draft (the panel has no draft-editing UI) and
  // asserted action "accept" — ported under an honest name, same assertions.
  it("sends accept feedback after rating submission", async () => {
    await mockStreamText("Original text.");

    renderWithProviders(<GenerationPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("generationPanel.generate"));

    await waitFor(() => {
      expect(screen.getByText("aiActions.accept")).toBeDefined();
    });

    // Accept
    fireEvent.click(screen.getByText("aiActions.accept"));

    await waitFor(() => {
      expect(screen.getByText("aiActions.rating")).toBeDefined();
    });

    // Submit rating to trigger feedback
    fireEvent.click(screen.getByRole("button", { name: "5" }));
    fireEvent.click(screen.getByText("aiActions.submitRating"));

    // Feedback should have been recorded
    await waitFor(() => {
      expect(mockRecordFeedbackMutate).toHaveBeenCalled();
      const feedbackCall = mockRecordFeedbackMutate.mock.calls[0][0];
      expect(feedbackCall.action).toBe("accept");
      expect(feedbackCall.project_id).toBe("novel-1");
    });
  });

  it("shows LearningStatus badge", () => {
    renderWithProviders(<GenerationPanel {...defaultProps} />);
    // LearningStatus is mocked to render a test-id span
    expect(screen.getByTestId("learning-status")).toBeDefined();
    expect(screen.getByTestId("learning-status").textContent).toBe("10");
  });

  it("sends enriched context (chapter_id, mode) with feedback", async () => {
    await mockStreamText("Some draft.");

    renderWithProviders(<GenerationPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("generationPanel.generate"));

    await waitFor(() => {
      expect(screen.getByText("aiActions.reject")).toBeDefined();
    });

    fireEvent.click(screen.getByText("aiActions.reject"));

    await waitFor(() => {
      expect(screen.getByText("aiActions.rating")).toBeDefined();
    });

    // Dismiss rating (skip) — this triggers feedback
    fireEvent.click(screen.getByText("aiActions.skipRating"));

    await waitFor(() => {
      expect(mockRecordFeedbackMutate).toHaveBeenCalled();
      const feedbackCall = mockRecordFeedbackMutate.mock.calls[0][0];
      // Enriched context should include chapter_id and mode
      expect(feedbackCall.chapter_id).toBe("chapter-1");
      expect(feedbackCall.mode).toBe("full_draft");
      expect(feedbackCall.project_id).toBe("novel-1");
    });
  });
});
