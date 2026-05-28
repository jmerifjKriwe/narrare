/**
 * SentimentPanel tests — ANAL-002
 *
 * Tests: loading state, close handler, results with VAD gauges,
 * error with retry, multi-chapter tabs, refresh, empty chapterIds.
 *
 * Mocking strategy:
 * - useSentimentAnalyze: controlled mutateAsync (never resolves / resolves / rejects)
 * - useEditorStore: mock selectors (setSentimentResult, setSentimentLoading)
 * - html-to-image: mock toPng for chart export
 * - Child components (SentimentChart, SentimentArcGraph): mock as stubs
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly).
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import { SentimentPanel } from "./SentimentPanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockMutateAsync: Mock;

vi.mock("@/lib/hooks/useSentiment", () => ({
  useSentimentAnalyze: () => ({
    mutateAsync: (...args: unknown[]) => mockMutateAsync(...args),
    isPending: false,
  }),
}));

const mockSetSentimentResult = vi.fn();
const mockSetSentimentLoading = vi.fn();

vi.mock("@/lib/stores/editorStore", () => ({
  useEditorStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      setSentimentResult: mockSetSentimentResult,
      setSentimentLoading: mockSetSentimentLoading,
    }),
}));

vi.mock("html-to-image", () => ({
  toPng: vi.fn().mockResolvedValue("data:image/png;base64,test"),
}));

vi.mock("./SentimentChart", () => ({
  SentimentChart: () => <div data-testid="sentiment-chart" />,
}));

vi.mock("./SentimentArcGraph", () => ({
  SentimentArcGraph: () => <div data-testid="sentiment-arc-graph" />,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeSentimentOverview(
  overrides: Record<string, unknown> = {},
): import("@/lib/api/analysis").SentimentOverview {
  return {
    sentence_count: 3,
    average_vad: { valence: 0.5, arousal: 0.3, dominance: 0.7 },
    overall_emotions: {
      anger: 0.1,
      anticipation: 0.2,
      disgust: 0.05,
      fear: 0.1,
      joy: 0.6,
      sadness: 0.15,
      surprise: 0.1,
      trust: 0.5,
      positive: 0.7,
      negative: 0.1,
    },
    narrative_arc: {
      arc_type: "Rise",
      confidence: 0.85,
      segments: [],
      explanation: "A steadily rising emotional trajectory.",
    },
    sentences: [
      {
        sentence: "The sun rose over the hills.",
        sentence_index: 0,
        vad: { valence: 0.6, arousal: 0.2, dominance: 0.5 },
        emotions: {
          anger: 0,
          anticipation: 0.1,
          disgust: 0,
          fear: 0,
          joy: 0.5,
          sadness: 0,
          surprise: 0,
          trust: 0.3,
          positive: 0.6,
          negative: 0,
        },
        word_count: 6,
        is_dialogue: false,
        dominant_emotion: "joy",
      },
      {
        sentence: "She smiled at the memory.",
        sentence_index: 1,
        vad: { valence: 0.7, arousal: 0.3, dominance: 0.6 },
        emotions: {
          anger: 0,
          anticipation: 0,
          disgust: 0,
          fear: 0,
          joy: 0.7,
          sadness: 0,
          surprise: 0,
          trust: 0.4,
          positive: 0.8,
          negative: 0,
        },
        word_count: 5,
        is_dialogue: false,
        dominant_emotion: "joy",
      },
      {
        sentence: '"I remember," she whispered.',
        sentence_index: 2,
        vad: { valence: 0.4, arousal: 0.5, dominance: 0.8 },
        emotions: {
          anger: 0,
          anticipation: 0.1,
          disgust: 0,
          fear: 0,
          joy: 0.3,
          sadness: 0.2,
          surprise: 0,
          trust: 0.5,
          positive: 0.4,
          negative: 0.1,
        },
        word_count: 4,
        is_dialogue: true,
        dominant_emotion: "joy",
      },
    ],
    dominant_emotions: ["joy"],
    ...overrides,
  };
}

const defaultProps = {
  novelId: "novel-1",
  chapterIds: ["ch-1"],
  onClose: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SentimentPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  it("renders loading state on mount when analysis is pending", () => {
    // mutateAsync never resolves → component stays in loading state
    mockMutateAsync = vi.fn(() => new Promise(() => {}));

    render(<SentimentPanel {...defaultProps} />);

    expect(screen.getByText("sentiment.loading")).toBeInTheDocument();
    expect(screen.getByText("sentiment.loadingSubtext")).toBeInTheDocument();
  });

  it("calls setSentimentLoading(true) while loading", () => {
    mockMutateAsync = vi.fn(() => new Promise(() => {}));

    render(<SentimentPanel {...defaultProps} />);

    expect(mockSetSentimentLoading).toHaveBeenCalledWith(true);
  });

  // -------------------------------------------------------------------------
  // Close handler
  // -------------------------------------------------------------------------

  it("calls onClose when close button (X) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    mockMutateAsync = vi.fn(() => new Promise(() => {}));

    render(<SentimentPanel {...defaultProps} onClose={onClose} />);

    // There are two close buttons (ArrowLeft and X) — click the X one
    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[closeButtons.length - 1]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when back button (ArrowLeft) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    mockMutateAsync = vi.fn(() => new Promise(() => {}));

    render(<SentimentPanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[0]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  // -------------------------------------------------------------------------
  // Results state
  // -------------------------------------------------------------------------

  it("renders VAD gauges after successful analysis", async () => {
    const result = [makeSentimentOverview()];
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<SentimentPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("sentiment.vad.title")).toBeInTheDocument();
    });

    // VAD gauge values (formatted to 2 decimal places)
    expect(screen.getByText("0.50")).toBeInTheDocument(); // valence
    expect(screen.getByText("0.30")).toBeInTheDocument(); // arousal
    expect(screen.getByText("0.70")).toBeInTheDocument(); // dominance
  });

  it("renders sentence breakdown in results", async () => {
    const result = [makeSentimentOverview()];
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<SentimentPanel {...defaultProps} />);

    await waitFor(() => {
      // Sentence heading with the i18n key
      expect(screen.getByText("sentiment.sentences")).toBeInTheDocument();
    });
  });

  it("stores result in editor store on success", async () => {
    const result = [makeSentimentOverview()];
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<SentimentPanel {...defaultProps} />);

    await waitFor(() => {
      expect(mockSetSentimentResult).toHaveBeenCalledWith(result);
    });
    expect(mockSetSentimentLoading).toHaveBeenLastCalledWith(false);
  });

  // -------------------------------------------------------------------------
  // Error state
  // -------------------------------------------------------------------------

  it("renders error state with retry button when analysis fails", async () => {
    mockMutateAsync = vi.fn().mockRejectedValue(new Error("Network error"));

    render(<SentimentPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("error")).toBeInTheDocument();
    });
    expect(screen.getByText("Network error")).toBeInTheDocument();
    expect(screen.getByText("retry")).toBeInTheDocument();
  });

  it("retry button triggers re-analysis", async () => {
    const user = userEvent.setup();
    // First call fails, second succeeds
    mockMutateAsync = vi
      .fn()
      .mockRejectedValueOnce(new Error("fail"))
      .mockResolvedValueOnce([makeSentimentOverview()]);

    render(<SentimentPanel {...defaultProps} />);

    // Wait for error state
    await waitFor(() => {
      expect(screen.getByText("retry")).toBeInTheDocument();
    });

    // Click retry
    await user.click(screen.getByText("retry"));

    // Should have been called twice (initial + retry)
    expect(mockMutateAsync).toHaveBeenCalledTimes(2);
  });

  // -------------------------------------------------------------------------
  // Multi-chapter tabs
  // -------------------------------------------------------------------------

  it("shows chapter tabs when results have multiple chapters", async () => {
    const multiChapterResult = [
      makeSentimentOverview({ sentence_count: 2 }),
      makeSentimentOverview({ sentence_count: 5 }),
    ];
    mockMutateAsync = vi.fn().mockResolvedValue(multiChapterResult);

    render(<SentimentPanel {...defaultProps} chapterIds={["ch-1", "ch-2"]} />);

    await waitFor(() => {
      // Chapter tabs should be visible — the i18n key for chapter tab
      const chapterButtons = screen.getAllByText("sentiment.chapter");
      expect(chapterButtons.length).toBe(2);
    });
  });

  it("does not show chapter tabs for single chapter result", async () => {
    const singleResult = [makeSentimentOverview()];
    mockMutateAsync = vi.fn().mockResolvedValue(singleResult);

    render(<SentimentPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("sentiment.vad.title")).toBeInTheDocument();
    });

    expect(screen.queryByText(/sentiment.chapter/)).not.toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Refresh
  // -------------------------------------------------------------------------

  it("refresh button triggers re-analysis in results state", async () => {
    const user = userEvent.setup();
    const result = [makeSentimentOverview()];
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<SentimentPanel {...defaultProps} />);

    // Wait for results
    await waitFor(() => {
      expect(screen.getByText("refresh")).toBeInTheDocument();
    });

    // Click refresh
    await user.click(screen.getByText("refresh"));

    // Should have been called twice (initial auto-trigger + refresh)
    expect(mockMutateAsync).toHaveBeenCalledTimes(2);
  });

  // -------------------------------------------------------------------------
  // Empty chapterIds
  // -------------------------------------------------------------------------

  it("handles empty chapterIds gracefully without triggering analysis", () => {
    mockMutateAsync = vi.fn(() => new Promise(() => {}));

    render(<SentimentPanel {...defaultProps} chapterIds={[]} />);

    // mutateAsync should NOT have been called because runAnalysis guards against empty ids
    expect(mockMutateAsync).not.toHaveBeenCalled();
  });

  // -------------------------------------------------------------------------
  // Chart export
  // -------------------------------------------------------------------------

  it("renders export chart button in results state", async () => {
    const result = [makeSentimentOverview()];
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<SentimentPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByLabelText("sentiment.exportChart")).toBeInTheDocument();
    });
  });
});
