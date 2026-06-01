/**
 * ReadabilityPanel tests — ANAL-003
 *
 * Tests: loading state, close handler, results with metrics, genre comparison,
 * sentence analyses, error with retry, multi-chapter tabs, empty chapterIds.
 *
 * Mocking strategy:
 * - useReadabilityAnalysis: controlled mutateAsync (never resolves / resolves / rejects)
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly).
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type { ReadabilityResult } from "@/lib/api/analysis";
import { ReadabilityPanel } from "./ReadabilityPanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockMutateAsync: Mock;

vi.mock("@/lib/hooks/useReadability", () => ({
  useReadabilityAnalysis: () => ({
    mutateAsync: (...args: unknown[]) => mockMutateAsync(...args),
    isPending: false,
  }),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeReadabilityResult(overrides: Record<string, unknown> = {}): ReadabilityResult {
  return {
    metrics: {
      flesch_reading_ease: 72.5,
      flesch_kincaid_grade: 6.2,
      gunning_fog: 8.1,
      avg_sentence_length: 14.3,
      avg_syllables_per_word: 1.4,
      complex_word_ratio: 0.08,
      word_count: 1250,
      sentence_count: 87,
    },
    sentence_analyses: [
      {
        sentence:
          "This is a particularly convoluted and unnecessarily verbose sentence that drags on far longer than it should.",
        sentence_index: 5,
        issues: ["Sentence too long", "Complex vocabulary"],
        readability_score: 0.25,
        suggestions: [
          "This sentence is overly long and complex.",
          "This long, winding sentence goes on needlessly.",
        ],
      },
      {
        sentence: "She walked to the store.",
        sentence_index: 12,
        issues: [],
        readability_score: 0.95,
        suggestions: [],
      },
    ],
    genre_benchmarks: {
      middle_grade: {
        flesch_reading_ease: 80,
        flesch_kincaid_grade: 5,
        gunning_fog: 7,
        avg_sentence_length: 12,
        avg_syllables_per_word: 1.3,
        complex_word_ratio: 0.05,
        word_count: 0,
        sentence_count: 0,
      },
      young_adult: {
        flesch_reading_ease: 70,
        flesch_kincaid_grade: 7,
        gunning_fog: 9,
        avg_sentence_length: 15,
        avg_syllables_per_word: 1.5,
        complex_word_ratio: 0.1,
        word_count: 0,
        sentence_count: 0,
      },
    },
    overall_assessment: "The text is well-written with good readability overall.",
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

describe("ReadabilityPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  it("renders loading state on mount when analysis is pending", () => {
    mockMutateAsync = vi.fn(() => new Promise(() => {}));

    render(<ReadabilityPanel {...defaultProps} />);

    expect(screen.getByText("readability.analyzing")).toBeInTheDocument();
    expect(screen.getByText("readability.analyzingSubtext")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Close handler
  // -------------------------------------------------------------------------

  it("calls onClose when close button (X) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    mockMutateAsync = vi.fn(() => new Promise(() => {}));

    render(<ReadabilityPanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[closeButtons.length - 1]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when back button (ArrowLeft) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    mockMutateAsync = vi.fn(() => new Promise(() => {}));

    render(<ReadabilityPanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[0]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  // -------------------------------------------------------------------------
  // Results state
  // -------------------------------------------------------------------------

  it("renders readability scores after successful analysis", async () => {
    const result = [makeReadabilityResult()];
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<ReadabilityPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("readability.scores")).toBeInTheDocument();
    });

    // Score values (formatted to 1 decimal)
    expect(screen.getByText("72.5")).toBeInTheDocument();
  });

  it("renders text statistics after successful analysis", async () => {
    const result = [makeReadabilityResult()];
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<ReadabilityPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("readability.statistics")).toBeInTheDocument();
    });

    // Word count (1250) and sentence count (87) — toLocaleString format varies
    expect(screen.getByText(/1[.,]?250/)).toBeInTheDocument();
    expect(screen.getByText("87")).toBeInTheDocument();
  });

  it("renders genre comparison after successful analysis", async () => {
    const result = [makeReadabilityResult()];
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<ReadabilityPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("readability.genreComparison")).toBeInTheDocument();
    });

    // Genre labels
    expect(screen.getByText("readability.middleGrade")).toBeInTheDocument();
    expect(screen.getByText("readability.youngAdult")).toBeInTheDocument();
  });

  it("renders problematic sentences heading with count", async () => {
    const result = [makeReadabilityResult()];
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<ReadabilityPanel {...defaultProps} />);

    await waitFor(() => {
      // The i18n key with {count} param gets interpolated as "readability.problematicSentences" with count=2
      expect(screen.getByText("readability.problematicSentences")).toBeInTheDocument();
    });
  });

  it("renders overall assessment", async () => {
    const result = [makeReadabilityResult()];
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<ReadabilityPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("readability.overallAssessment")).toBeInTheDocument();
    });

    expect(
      screen.getByText("The text is well-written with good readability overall."),
    ).toBeInTheDocument();
  });

  it("shows no issues message when sentence analyses is empty", async () => {
    const result = [makeReadabilityResult({ sentence_analyses: [] })];
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<ReadabilityPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("readability.noIssues")).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Error state
  // -------------------------------------------------------------------------

  it("renders error state with retry button when analysis fails", async () => {
    mockMutateAsync = vi.fn().mockRejectedValue(new Error("Network error"));

    render(<ReadabilityPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("readability.error")).toBeInTheDocument();
    });
    expect(screen.getByText("Network error")).toBeInTheDocument();
    expect(screen.getByText("retry")).toBeInTheDocument();
  });

  it("retry button triggers re-analysis", async () => {
    const user = userEvent.setup();
    mockMutateAsync = vi
      .fn()
      .mockRejectedValueOnce(new Error("fail"))
      .mockResolvedValueOnce([makeReadabilityResult()]);

    render(<ReadabilityPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("retry")).toBeInTheDocument();
    });

    await user.click(screen.getByText("retry"));

    expect(mockMutateAsync).toHaveBeenCalledTimes(2);
  });

  // -------------------------------------------------------------------------
  // Multi-chapter tabs
  // -------------------------------------------------------------------------

  it("shows chapter tabs when results have multiple chapters", async () => {
    const multiChapterResult = [
      makeReadabilityResult({
        metrics: {
          flesch_reading_ease: 72.5,
          flesch_kincaid_grade: 6.2,
          gunning_fog: 8.1,
          avg_sentence_length: 14.3,
          avg_syllables_per_word: 1.4,
          complex_word_ratio: 0.08,
          word_count: 1250,
          sentence_count: 87,
        },
      }),
      makeReadabilityResult({
        metrics: {
          flesch_reading_ease: 65.0,
          flesch_kincaid_grade: 7.5,
          gunning_fog: 10.2,
          avg_sentence_length: 16.1,
          avg_syllables_per_word: 1.6,
          complex_word_ratio: 0.12,
          word_count: 2100,
          sentence_count: 130,
        },
      }),
    ];
    mockMutateAsync = vi.fn().mockResolvedValue(multiChapterResult);

    render(<ReadabilityPanel {...defaultProps} chapterIds={["ch-1", "ch-2"]} />);

    await waitFor(() => {
      const chapterButtons = screen.getAllByText("readability.chapter");
      expect(chapterButtons.length).toBe(2);
    });
  });

  it("does not show chapter tabs for single chapter result", async () => {
    const singleResult = [makeReadabilityResult()];
    mockMutateAsync = vi.fn().mockResolvedValue(singleResult);

    render(<ReadabilityPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("readability.scores")).toBeInTheDocument();
    });

    expect(screen.queryByText(/readability.chapter/)).not.toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Refresh
  // -------------------------------------------------------------------------

  it("refresh button triggers re-analysis in results state", async () => {
    const user = userEvent.setup();
    const result = [makeReadabilityResult()];
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<ReadabilityPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("refresh")).toBeInTheDocument();
    });

    await user.click(screen.getByText("refresh"));

    expect(mockMutateAsync).toHaveBeenCalledTimes(2);
  });

  // -------------------------------------------------------------------------
  // Empty chapterIds
  // -------------------------------------------------------------------------

  it("handles empty chapterIds gracefully without triggering analysis", () => {
    mockMutateAsync = vi.fn(() => new Promise(() => {}));

    render(<ReadabilityPanel {...defaultProps} chapterIds={[]} />);

    expect(mockMutateAsync).not.toHaveBeenCalled();
  });
});
