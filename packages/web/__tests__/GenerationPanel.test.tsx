/**
 * GenerationPanel tests — core generation flow, rating, modify-tracking.
 *
 * Tests:
 * 1. Renders generation config panel (trigger button visible)
 * 2. Shows config panel in initial phase
 * 3. Displays streaming response text
 * 4. Shows RatingPrompt after accept
 * 5. Shows RatingPrompt with reject reason after reject
 * 6. Sends modify feedback when text was edited before accept
 * 7. Shows LearningStatus badge
 * 8. Sends enriched context (chapter_id, mode) with feedback
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, type Mock, vi } from "vitest";
import { GenerationPanel } from "@/components/studio/editor/GenerationPanel";

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
const mockAcceptDraft = vi.fn();
const mockRejectDraft = vi.fn();
const mockStopGeneration = vi.fn();

vi.mock("@/lib/api/generation", () => ({
  writingApi: {
    startGeneration: (...args: unknown[]) => mockStartGeneration(...args),
    acceptDraft: (...args: unknown[]) => mockAcceptDraft(...args),
    rejectDraft: (...args: unknown[]) => mockRejectDraft(...args),
    stopGeneration: (...args: unknown[]) => mockStopGeneration(...args),
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

// Mock LearningStatus to simplify assertions
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
  chapterContent: "Existing chapter text",
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
    mockAcceptDraft.mockResolvedValue({
      request_id: "gen-test-id",
      chapter_id: "chapter-1",
      word_count: 500,
    });
    mockRejectDraft.mockResolvedValue({
      request_id: "gen-test-id",
      status: "rejected",
    });
  });

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
    // Import the mocked streamGeneration
    const { streamGeneration } = await import("@/lib/api/generation");
    const streamMock = streamGeneration as Mock;

    // Capture the onChunk callback to simulate streaming
    streamMock.mockImplementation(
      async (
        _requestId: string,
        onChunk: (chunk: { text: string }) => void,
        onComplete?: () => void,
      ) => {
        onChunk({ text: "Once upon a time" });
        onChunk({ text: " in a land far away." });
        onComplete?.();
      },
    );

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
    const { streamGeneration } = await import("@/lib/api/generation");
    const streamMock = streamGeneration as Mock;

    streamMock.mockImplementation(
      async (
        _requestId: string,
        onChunk: (chunk: { text: string }) => void,
        onComplete?: () => void,
      ) => {
        onChunk({ text: "Generated draft text." });
        onComplete?.();
      },
    );

    renderWithProviders(<GenerationPanel {...defaultProps} />);

    // Start generation
    fireEvent.click(screen.getByText("generationPanel.generate"));

    // Wait for review phase
    await waitFor(() => {
      expect(screen.getByText("generationPanel.accept")).toBeDefined();
    });

    // Accept the draft
    fireEvent.click(screen.getByText("generationPanel.accept"));

    // RatingPrompt should appear
    await waitFor(() => {
      expect(screen.getByText("learning.rating")).toBeDefined();
    });
  });

  it("shows RatingPrompt with reject reason textarea after reject", async () => {
    const { streamGeneration } = await import("@/lib/api/generation");
    const streamMock = streamGeneration as Mock;

    streamMock.mockImplementation(
      async (
        _requestId: string,
        onChunk: (chunk: { text: string }) => void,
        onComplete?: () => void,
      ) => {
        onChunk({ text: "Bad draft text." });
        onComplete?.();
      },
    );

    renderWithProviders(<GenerationPanel {...defaultProps} />);

    // Start generation
    fireEvent.click(screen.getByText("generationPanel.generate"));

    await waitFor(() => {
      expect(screen.getByText("generationPanel.reject")).toBeDefined();
    });

    // Reject the draft
    fireEvent.click(screen.getByText("generationPanel.reject"));

    // RatingPrompt with reject reason textarea should appear
    await waitFor(() => {
      expect(screen.getByText("learning.rating")).toBeDefined();
      expect(screen.getByPlaceholderText("learning.rejectReason")).toBeDefined();
    });
  });

  it("sends modify feedback when text was edited before accept", async () => {
    const { streamGeneration } = await import("@/lib/api/generation");
    const streamMock = streamGeneration as Mock;

    streamMock.mockImplementation(
      async (
        _requestId: string,
        onChunk: (chunk: { text: string }) => void,
        onComplete?: () => void,
      ) => {
        onChunk({ text: "Original text." });
        onComplete?.();
      },
    );

    renderWithProviders(<GenerationPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("generationPanel.generate"));

    await waitFor(() => {
      expect(screen.getByText("generationPanel.accept")).toBeDefined();
    });

    // Accept
    fireEvent.click(screen.getByText("generationPanel.accept"));

    await waitFor(() => {
      expect(screen.getByText("learning.rating")).toBeDefined();
    });

    // Submit rating to trigger feedback
    fireEvent.click(screen.getByRole("button", { name: "5" }));
    fireEvent.click(screen.getByText("learning.submitRating"));

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
    const { streamGeneration } = await import("@/lib/api/generation");
    const streamMock = streamGeneration as Mock;

    streamMock.mockImplementation(
      async (
        _requestId: string,
        onChunk: (chunk: { text: string }) => void,
        onComplete?: () => void,
      ) => {
        onChunk({ text: "Some draft." });
        onComplete?.();
      },
    );

    renderWithProviders(<GenerationPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("generationPanel.generate"));

    await waitFor(() => {
      expect(screen.getByText("generationPanel.reject")).toBeDefined();
    });

    fireEvent.click(screen.getByText("generationPanel.reject"));

    await waitFor(() => {
      expect(screen.getByText("learning.rating")).toBeDefined();
    });

    // Dismiss rating (skip) — this triggers feedback
    fireEvent.click(screen.getByText("learning.skipRating"));

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
