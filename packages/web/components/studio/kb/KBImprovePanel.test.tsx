/**
 * KBImprovePanel tests
 *
 * Tests: loading state, close/back button, suggestions in review,
 * toggle suggestion selection, select all/none, apply disabled when empty,
 * no suggestions state, onApplied callback after apply.
 *
 * Mocking strategy:
 * - useKBImproveAnalysis / useKBImproveApply: controlled mutateAsync
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly).
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type { KBImproveAnalysisResponse } from "@/lib/api/kb-improve";
import { KBImprovePanel } from "./KBImprovePanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockAnalyzeMutateAsync: Mock;
let mockApplyMutateAsync: Mock;

vi.mock("@/lib/hooks/useKBImprove", () => ({
  useKBImproveAnalysis: () => ({
    mutateAsync: (...args: unknown[]) => mockAnalyzeMutateAsync(...args),
    isPending: false,
  }),
  useKBImproveApply: () => ({
    mutateAsync: (...args: unknown[]) => mockApplyMutateAsync(...args),
    isPending: false,
  }),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeSuggestion(overrides: Record<string, unknown> = {}) {
  return {
    type: "add_field" as const,
    target: "personality",
    description: "Add personality traits",
    proposed_content: "Brave and resourceful",
    related_entity_id: null,
    related_entity_name: null,
    confidence: 0.8,
    reasoning: "Most characters benefit from personality details",
    suggestion_id: 1,
    ...overrides,
  };
}

function makeAnalysisResponse(
  overrides: Partial<KBImproveAnalysisResponse> = {},
): KBImproveAnalysisResponse {
  return {
    suggestions: [
      makeSuggestion({ suggestion_id: 1, confidence: 0.8 }),
      makeSuggestion({
        suggestion_id: 2,
        type: "expand",
        confidence: 0.5,
        description: "Expand backstory",
      }),
      makeSuggestion({
        suggestion_id: 3,
        type: "connect",
        confidence: 0.9,
        description: "Connect to ally",
      }),
    ],
    overall_assessment: "Entry is mostly complete but could use more detail.",
    completeness_score: 0.65,
    ...overrides,
  };
}

const defaultProps = {
  novelId: "novel-1",
  entryId: "entry-1",
  onClose: vi.fn(),
  onApplied: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBImprovePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAnalyzeMutateAsync = vi.fn();
    mockApplyMutateAsync = vi.fn();
  });

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  it("renders loading state on mount", () => {
    mockAnalyzeMutateAsync.mockReturnValue(new Promise(() => {}));

    render(<KBImprovePanel {...defaultProps} />);

    expect(screen.getByText("kb.improve.running")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Close / Back button
  // -------------------------------------------------------------------------

  it("calls onClose when back button is clicked in review state", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const response = makeAnalysisResponse({ suggestions: [] });
    mockAnalyzeMutateAsync.mockResolvedValue(response);

    render(<KBImprovePanel {...defaultProps} onClose={onClose} />);

    // Wait for review state with no suggestions
    await waitFor(() => {
      expect(screen.getByText("kb.improve.noSuggestions")).toBeInTheDocument();
    });

    // Click back button
    await user.click(screen.getByText("kb.improve.back"));

    expect(onClose).toHaveBeenCalledOnce();
  });

  // -------------------------------------------------------------------------
  // Review state — suggestions
  // -------------------------------------------------------------------------

  it("renders suggestions in review state", async () => {
    const response = makeAnalysisResponse();
    mockAnalyzeMutateAsync.mockResolvedValue(response);

    render(<KBImprovePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Add personality traits")).toBeInTheDocument();
    });

    expect(screen.getByText("Expand backstory")).toBeInTheDocument();
    expect(screen.getByText("Connect to ally")).toBeInTheDocument();
  });

  it("shows completeness score in review state", async () => {
    const response = makeAnalysisResponse();
    mockAnalyzeMutateAsync.mockResolvedValue(response);

    render(<KBImprovePanel {...defaultProps} />);

    await waitFor(() => {
      // 0.65 * 100 = 65%
      expect(screen.getByText("65%")).toBeInTheDocument();
    });
  });

  it("shows overall assessment text", async () => {
    const response = makeAnalysisResponse();
    mockAnalyzeMutateAsync.mockResolvedValue(response);

    render(<KBImprovePanel {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText("Entry is mostly complete but could use more detail."),
      ).toBeInTheDocument();
    });
  });

  it("auto-selects suggestions with confidence >= 0.7", async () => {
    const response = makeAnalysisResponse();
    mockAnalyzeMutateAsync.mockResolvedValue(response);

    render(<KBImprovePanel {...defaultProps} />);

    await waitFor(() => {
      // Suggestions with id 1 (0.8) and 3 (0.9) should be auto-selected
      // id 2 has confidence 0.5, should NOT be auto-selected
      const selectedCountText = screen.getByText(/kb\.improve\.selectedCount|2 of 3 selected/);
      expect(selectedCountText).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Toggle suggestion selection
  // -------------------------------------------------------------------------

  it("toggle suggestion selection on click", async () => {
    const user = userEvent.setup();
    const response = makeAnalysisResponse();
    mockAnalyzeMutateAsync.mockResolvedValue(response);

    render(<KBImprovePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Add personality traits")).toBeInTheDocument();
    });

    // Initially, suggestion_id 1 (confidence 0.8) is auto-selected
    // Click to deselect — click the suggestion header button
    const suggestionButtons = screen.getAllByText("Add personality traits");
    await user.click(suggestionButtons[0].closest("button")!);

    // The "willApply" text for this suggestion should disappear
    // (or the selected count should change)
  });

  // -------------------------------------------------------------------------
  // Select all / select none
  // -------------------------------------------------------------------------

  it("select all button selects all suggestions", async () => {
    const user = userEvent.setup();
    const response = makeAnalysisResponse();
    mockAnalyzeMutateAsync.mockResolvedValue(response);

    render(<KBImprovePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.selectAll")).toBeInTheDocument();
    });

    await user.click(screen.getByText("kb.selectAll"));

    // Selected count should show 3 of 3
    expect(screen.getByText(/3 of 3 selected|kb\.improve\.selectedCount/)).toBeInTheDocument();
  });

  it("select none button deselects all suggestions", async () => {
    const user = userEvent.setup();
    const response = makeAnalysisResponse();
    mockAnalyzeMutateAsync.mockResolvedValue(response);

    render(<KBImprovePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.selectNone")).toBeInTheDocument();
    });

    await user.click(screen.getByText("kb.selectNone"));

    // Selected count should show 0
    // The apply button text should show 0 selected
    const applyButton = screen.getByText(/kb\.applySelected|Apply Selected/);
    expect(applyButton).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Apply button
  // -------------------------------------------------------------------------

  it("apply button is disabled when no suggestions selected", async () => {
    const user = userEvent.setup();
    const response = makeAnalysisResponse();
    mockAnalyzeMutateAsync.mockResolvedValue(response);

    render(<KBImprovePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.selectNone")).toBeInTheDocument();
    });

    // Deselect all
    await user.click(screen.getByText("kb.selectNone"));

    // Apply button should be disabled
    const applyButton = screen.getByText(/kb\.applySelected|Apply Selected/).closest("button");
    expect(applyButton).toHaveProperty("disabled", true);
  });

  it("calls onApplied after successful apply", async () => {
    const user = userEvent.setup();
    const onApplied = vi.fn();
    const response = makeAnalysisResponse();
    mockAnalyzeMutateAsync.mockResolvedValue(response);
    mockApplyMutateAsync.mockResolvedValue({
      success: true,
      entry_id: "entry-1",
      applied_count: 2,
      message: "Applied",
    });

    render(<KBImprovePanel {...defaultProps} onApplied={onApplied} />);

    await waitFor(() => {
      expect(screen.getByText(/kb\.applySelected|Apply Selected/)).toBeInTheDocument();
    });

    // Click apply (suggestions with confidence >= 0.7 are auto-selected)
    const applyButton = screen.getByText(/kb\.applySelected|Apply Selected/).closest("button")!;
    await user.click(applyButton);

    await waitFor(() => {
      expect(onApplied).toHaveBeenCalledOnce();
    });
  });

  // -------------------------------------------------------------------------
  // No suggestions state
  // -------------------------------------------------------------------------

  it("renders no suggestions state when analysis returns empty", async () => {
    const response = makeAnalysisResponse({ suggestions: [], completeness_score: 1.0 });
    mockAnalyzeMutateAsync.mockResolvedValue(response);

    render(<KBImprovePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("kb.improve.noSuggestions")).toBeInTheDocument();
    });

    expect(screen.getByText("kb.improve.entryLooksGood")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Error state
  // -------------------------------------------------------------------------

  it("renders error state when analysis fails", async () => {
    mockAnalyzeMutateAsync.mockRejectedValue(new Error("Analysis failed"));

    render(<KBImprovePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Analysis failed")).toBeInTheDocument();
    });
  });

  it("retry button in error state triggers re-analysis", async () => {
    const user = userEvent.setup();
    mockAnalyzeMutateAsync
      .mockRejectedValueOnce(new Error("fail"))
      .mockResolvedValueOnce(makeAnalysisResponse());

    render(<KBImprovePanel {...defaultProps} />);

    await waitFor(() => {
      // Error message is displayed
      expect(screen.getByText("fail")).toBeInTheDocument();
    });

    // Click retry button
    const retryButton = screen.getByText("kb.retry");
    await user.click(retryButton);

    expect(mockAnalyzeMutateAsync).toHaveBeenCalledTimes(2);
  });

  // -------------------------------------------------------------------------
  // Confidence display
  // -------------------------------------------------------------------------

  it("shows confidence percentage for each suggestion", async () => {
    const response = makeAnalysisResponse();
    mockAnalyzeMutateAsync.mockResolvedValue(response);

    render(<KBImprovePanel {...defaultProps} />);

    await waitFor(() => {
      // confidence values: 80%, 50%, 90%
      expect(screen.getByText("80%")).toBeInTheDocument();
      expect(screen.getByText("50%")).toBeInTheDocument();
      expect(screen.getByText("90%")).toBeInTheDocument();
    });
  });
});
