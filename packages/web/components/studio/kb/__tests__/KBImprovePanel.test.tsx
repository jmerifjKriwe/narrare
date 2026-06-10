/**
 * KBImprovePanel tests — AI-powered entry improvement review.
 *
 * Tests:
 * 1. Shows loading state on mount
 * 2. Shows error state with retry button
 * 3. Shows review state with suggestions
 * 4. Auto-selects high-confidence suggestions (>= 0.7)
 * 5. Toggle suggestion selection
 * 6. Select All / Select None buttons work
 * 7. Apply Selected calls onApplied on success
 * 8. Apply Selected shows error on failure
 * 9. Shows no-suggestions state
 * 10. Close button calls onClose
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBImprovePanel } from "@/components/studio/kb/KBImprovePanel";
import type {
  ImproveSuggestion,
  KBImproveAnalysisResponse,
  KBImproveApplyResponse,
} from "@/lib/api/kb-improve";
import { useKBImproveAnalysis, useKBImproveApply } from "@/lib/hooks/useKBImprove";

// Mock the hooks module — vitest hoists this to the top
vi.mock("@/lib/hooks/useKBImprove", () => ({
  useKBImproveAnalysis: vi.fn(),
  useKBImproveApply: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockSuggestions: ImproveSuggestion[] = [
  {
    suggestion_id: 1,
    type: "add_field",
    target: "personality",
    description: "Add personality traits field",
    proposed_content: "Brave, compassionate, and strategic",
    related_entity_id: null,
    related_entity_name: null,
    confidence: 0.85,
    reasoning: "Adding personality would enhance character depth",
  },
  {
    suggestion_id: 2,
    type: "expand",
    target: "backstory",
    description: "Expand backstory details",
    proposed_content: "Grew up in a small coastal village",
    related_entity_id: null,
    related_entity_name: null,
    confidence: 0.45,
    reasoning: "More backstory would add richness",
  },
];

const mockAnalysis: KBImproveAnalysisResponse = {
  suggestions: mockSuggestions,
  overall_assessment: "The entry is decent but could be improved",
  completeness_score: 0.65,
};

const mockApplyResponse: KBImproveApplyResponse = {
  success: true,
  entry_id: "entry-1",
  applied_count: 1,
  message: "Applied successfully",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPanel(overrides: { onClose?: () => void; onApplied?: () => void } = {}) {
  const onClose = overrides.onClose ?? vi.fn();
  const onApplied = overrides.onApplied ?? vi.fn();

  return {
    onClose,
    onApplied,
    ...render(
      <KBImprovePanel
        novelId="novel-1"
        entryId="entry-1"
        onClose={onClose}
        onApplied={onApplied}
      />,
    ),
  };
}

function setupReviewState() {
  const mockAnalyze = vi.fn().mockResolvedValue(mockAnalysis);
  (useKBImproveAnalysis as ReturnType<typeof vi.fn>).mockReturnValue({
    mutateAsync: mockAnalyze,
    isPending: false,
  });
  (useKBImproveApply as ReturnType<typeof vi.fn>).mockReturnValue({
    mutateAsync: vi.fn(),
    isPending: false,
  });
  return { mockAnalyze };
}

async function waitForReview() {
  await waitFor(() => {
    expect(screen.getByText("kb.improve.completeness")).toBeDefined();
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBImprovePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mocks — keep the promise pending so component stays in loading
    // unless overridden by the specific test.
    (useKBImproveAnalysis as ReturnType<typeof vi.fn>).mockReturnValue({
      mutateAsync: vi.fn().mockReturnValue(new Promise(() => {})),
      isPending: false,
    });
    (useKBImproveApply as ReturnType<typeof vi.fn>).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    });
  });

  // -----------------------------------------------------------------------
  // 1. Loading state
  // -----------------------------------------------------------------------

  it("shows loading state on mount", () => {
    const mockAnalyze = vi.fn().mockReturnValue(new Promise(() => {}));
    (useKBImproveAnalysis as ReturnType<typeof vi.fn>).mockReturnValue({
      mutateAsync: mockAnalyze,
      isPending: false,
    });

    renderPanel();

    expect(screen.getByText("kb.improve.running")).toBeDefined();
    expect(screen.getByText("kb.aiEnhancingDesc")).toBeDefined();
    expect(mockAnalyze).toHaveBeenCalledTimes(1);
  });

  // -----------------------------------------------------------------------
  // 2. Error state
  // -----------------------------------------------------------------------

  it("shows error state with retry button", async () => {
    const mockAnalyze = vi.fn().mockRejectedValue(new Error("Analysis failed"));
    (useKBImproveAnalysis as ReturnType<typeof vi.fn>).mockReturnValue({
      mutateAsync: mockAnalyze,
      isPending: false,
    });

    renderPanel();

    await waitFor(() => {
      // Error is now mapped to AIErrorResponse with i18n key
      expect(screen.getByText("aiActions.errorConnection")).toBeDefined();
    });

    expect(screen.getByText("aiActions.retry")).toBeDefined();
  });

  // -----------------------------------------------------------------------
  // 3. Review state
  // -----------------------------------------------------------------------

  it("shows review state with suggestions", async () => {
    setupReviewState();

    renderPanel();
    await waitForReview();

    // Completeness score
    expect(screen.getByText("65%")).toBeDefined();
    // Assessment
    expect(screen.getByText("The entry is decent but could be improved")).toBeDefined();
    // Suggestions count header
    expect(screen.getByText("kb.enhancementsFound")).toBeDefined();
    // Suggestion descriptions
    expect(screen.getByText("Add personality traits field")).toBeDefined();
    expect(screen.getByText("Expand backstory details")).toBeDefined();
    // Suggestion type labels
    expect(screen.getByText("add field")).toBeDefined();
    expect(screen.getByText("expand")).toBeDefined();
    // Reasoning text
    expect(screen.getByText("Adding personality would enhance character depth")).toBeDefined();
    expect(screen.getByText("More backstory would add richness")).toBeDefined();
  });

  // -----------------------------------------------------------------------
  // 4. Auto-select high confidence
  // -----------------------------------------------------------------------

  it("auto-selects high-confidence suggestions", async () => {
    setupReviewState();

    renderPanel();
    await waitForReview();

    // Suggestion 1 (confidence 0.85 >= 0.7) → selected → shows "Will apply"
    // Suggestion 2 (confidence 0.45 < 0.7)  → not selected
    const willApply = screen.getAllByText("kb.willApply");
    expect(willApply.length).toBe(1);
    // Verify it's next to the high-confidence suggestion
    expect(willApply[0].closest("button")?.textContent).toMatch(/Add personality traits field/);
  });

  // -----------------------------------------------------------------------
  // 5. Toggle selection
  // -----------------------------------------------------------------------

  it("toggles suggestion selection on click", async () => {
    setupReviewState();

    renderPanel();
    await waitForReview();

    // Start: 1 selected (suggestion 1 auto-selected)
    expect(screen.getAllByText("kb.willApply").length).toBe(1);

    // Click on suggestion 2 to select it
    fireEvent.click(screen.getByText("Expand backstory details"));

    await waitFor(() => {
      expect(screen.getAllByText("kb.willApply").length).toBe(2);
    });

    // Click again to deselect
    fireEvent.click(screen.getByText("Expand backstory details"));

    await waitFor(() => {
      expect(screen.getAllByText("kb.willApply").length).toBe(1);
    });
  });

  // -----------------------------------------------------------------------
  // 6. Select All / Select None
  // -----------------------------------------------------------------------

  it("Select All / Select None buttons work", async () => {
    setupReviewState();

    renderPanel();
    await waitForReview();

    // Start: 1 selected (auto-selected high confidence)
    expect(screen.getAllByText("kb.willApply").length).toBe(1);

    // Select None
    fireEvent.click(screen.getByText("kb.selectNone"));
    await waitFor(() => {
      expect(screen.queryAllByText("kb.willApply").length).toBe(0);
    });

    // Select All
    fireEvent.click(screen.getByText("kb.selectAll"));
    await waitFor(() => {
      expect(screen.getAllByText("kb.willApply").length).toBe(2);
    });
  });

  // -----------------------------------------------------------------------
  // 6b. Apply button disabled when no suggestions selected
  // -----------------------------------------------------------------------

  it("apply button is disabled when no suggestions selected", async () => {
    setupReviewState();

    renderPanel();
    await waitForReview();

    // Start: 1 selected (suggestion 1 auto-selected). Deselect all first.
    // Use fireEvent since we're in review state already
    fireEvent.click(screen.getByText("kb.selectNone"));

    await waitFor(() => {
      const applyButton = screen.getByText("kb.applySelected").closest("button");
      expect(applyButton).toHaveProperty("disabled", true);
    });
  });

  // -----------------------------------------------------------------------
  // 7. Apply Selected — success
  // -----------------------------------------------------------------------

  it("Apply Selected calls onApplied on success", async () => {
    setupReviewState();
    const mockApply = vi.fn().mockResolvedValue(mockApplyResponse);
    (useKBImproveApply as ReturnType<typeof vi.fn>).mockReturnValue({
      mutateAsync: mockApply,
      isPending: false,
    });

    const { onApplied, onClose } = renderPanel();
    await waitForReview();

    // Click "Apply Selected"
    fireEvent.click(screen.getByText("kb.applySelected"));

    // Should call mutateAsync with auto-selected IDs (suggestion_id 1)
    await waitFor(() => {
      expect(mockApply).toHaveBeenCalledWith([1]);
    });

    // Should call onApplied on success
    await waitFor(() => {
      expect(onApplied).toHaveBeenCalledTimes(1);
    });
    expect(onClose).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // 8. Apply Selected — error
  // -----------------------------------------------------------------------

  it("Apply Selected shows error on failure", async () => {
    setupReviewState();
    const mockApply = vi.fn().mockRejectedValue(new Error("Apply failed"));
    (useKBImproveApply as ReturnType<typeof vi.fn>).mockReturnValue({
      mutateAsync: mockApply,
      isPending: false,
    });

    const { onApplied } = renderPanel();
    await waitForReview();

    // Click "Apply Selected"
    fireEvent.click(screen.getByText("kb.applySelected"));

    // The error is now mapped to AIErrorResponse with i18n key
    await waitFor(() => {
      expect(screen.getByText("aiActions.errorConnection")).toBeDefined();
    });

    // The error retry button uses aiActions.retry
    expect(screen.getByText("aiActions.retry")).toBeDefined();

    // onApplied should NOT be called
    expect(onApplied).not.toHaveBeenCalled();
  });

  // -----------------------------------------------------------------------
  // 8b. Retry in error state
  // -----------------------------------------------------------------------

  it("retry button in error state triggers re-analysis", async () => {
    const mockAnalyze = vi
      .fn()
      .mockRejectedValueOnce(new Error("fail"))
      .mockResolvedValueOnce(mockAnalysis);
    (useKBImproveAnalysis as ReturnType<typeof vi.fn>).mockReturnValue({
      mutateAsync: mockAnalyze,
      isPending: false,
    });

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("aiActions.errorConnection")).toBeDefined();
    });

    // Click retry button
    fireEvent.click(screen.getByText("aiActions.retry"));

    await waitFor(() => {
      expect(mockAnalyze).toHaveBeenCalledTimes(2);
    });
  });

  // -----------------------------------------------------------------------
  // 9. No suggestions
  // -----------------------------------------------------------------------

  it("shows no-suggestions state", async () => {
    const emptyAnalysis: KBImproveAnalysisResponse = {
      suggestions: [],
      overall_assessment: "Entry is complete",
      completeness_score: 0.95,
    };
    const mockAnalyze = vi.fn().mockResolvedValue(emptyAnalysis);
    (useKBImproveAnalysis as ReturnType<typeof vi.fn>).mockReturnValue({
      mutateAsync: mockAnalyze,
      isPending: false,
    });

    renderPanel();

    await waitFor(() => {
      expect(screen.getByText("kb.improve.noSuggestions")).toBeDefined();
    });

    expect(screen.getByText("kb.improve.entryLooksGood")).toBeDefined();
    // Footer has only the "Back to Entry" button, NOT "Apply Selected"
    expect(screen.queryByText("kb.applySelected")).toBeNull();
  });

  // -----------------------------------------------------------------------
  // 10. Close button
  // -----------------------------------------------------------------------

  // -----------------------------------------------------------------------
  // 11. Confidence display
  // -----------------------------------------------------------------------

  it("shows confidence percentage for each suggestion", async () => {
    setupReviewState();

    renderPanel();
    await waitForReview();

    // confidence values: 85%, 45%
    expect(screen.getByText("85%")).toBeDefined();
    expect(screen.getByText("45%")).toBeDefined();
  });

  it("close button calls onClose", async () => {
    setupReviewState();

    const { onClose } = renderPanel();
    await waitForReview();

    // The header has an ArrowLeft icon button that calls onClose.
    // Find it via the lucide-arrow-left SVG within a button.
    const backButtons = screen
      .getAllByRole("button")
      .filter((btn) => btn.querySelector("svg.lucide-arrow-left"));
    expect(backButtons.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(backButtons[0]);

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
