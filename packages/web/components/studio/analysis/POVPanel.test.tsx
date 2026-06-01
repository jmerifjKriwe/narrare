/**
 * POVPanel tests — ANAL-004
 *
 * Tests: loading state, close handler, results with distribution/scenes/issues,
 * error with retry, expandable issue details, empty chapterIds.
 *
 * Mocking strategy:
 * - usePOVAnalysis: controlled mutateAsync (never resolves / resolves / rejects)
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly).
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type { POVResult } from "@/lib/api/analysis";
import { POVPanel } from "./POVPanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockMutateAsync: Mock;

vi.mock("@/lib/hooks/usePOV", () => ({
  usePOVAnalysis: () => ({
    mutateAsync: (...args: unknown[]) => mockMutateAsync(...args),
    isPending: false,
  }),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makePOVResult(overrides: Record<string, unknown> = {}): POVResult {
  return {
    scenes: [
      {
        scene_index: 0,
        start_position: 0,
        end_position: 500,
        pov_character: "Alice",
        confidence: 0.92,
      },
      {
        scene_index: 1,
        start_position: 501,
        end_position: 1200,
        pov_character: "Bob",
        confidence: 0.67,
      },
      {
        scene_index: 2,
        start_position: 1201,
        end_position: 1800,
        pov_character: null,
        confidence: 0.25,
      },
    ],
    issues: [
      {
        type: "head_hop",
        location: "Scene 1, paragraph 3",
        text: "Bob knew what Alice was thinking.",
        explanation: "The narrative suddenly accesses Alice's thoughts from Bob's POV.",
        suggestion: "Describe only what Bob can observe about Alice's behavior.",
        severity: "error",
      },
      {
        type: "knowledge_leak",
        location: "Scene 2, paragraph 1",
        text: "She was unaware of the danger lurking behind her.",
        explanation: "The narrator reveals information the POV character cannot know.",
        suggestion: "Remove the omniscient reveal or switch to omniscient narration.",
        severity: "warning",
      },
    ],
    pov_distribution: {
      Alice: 55.5,
      Bob: 35.2,
      Unknown: 9.3,
    },
    switch_count: 3,
    analysis_type: "third_limited",
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

describe("POVPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  it("renders loading state on mount when analysis is pending", () => {
    mockMutateAsync = vi.fn(() => new Promise(() => {}));

    render(<POVPanel {...defaultProps} />);

    expect(screen.getByText("pov.analyzing")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Close handler
  // -------------------------------------------------------------------------

  it("calls onClose when close button (X) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    mockMutateAsync = vi.fn(() => new Promise(() => {}));

    render(<POVPanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[closeButtons.length - 1]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when back button (ArrowLeft) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    mockMutateAsync = vi.fn(() => new Promise(() => {}));

    render(<POVPanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[0]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  // -------------------------------------------------------------------------
  // Results state
  // -------------------------------------------------------------------------

  it("renders summary stats after successful analysis", async () => {
    const result = makePOVResult();
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<POVPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("pov.analysisType")).toBeInTheDocument();
    });

    expect(screen.getByText("third limited")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument(); // switch_count
    expect(screen.getByText("2")).toBeInTheDocument(); // issues count
  });

  it("renders POV distribution after successful analysis", async () => {
    const result = makePOVResult();
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<POVPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("pov.distribution")).toBeInTheDocument();
    });

    // Distribution section contains character names + percentages
    const aliceElements = screen.getAllByText("Alice");
    expect(aliceElements.length).toBeGreaterThanOrEqual(2); // distribution + scene
    expect(screen.getByText("55.5%")).toBeInTheDocument();
    expect(screen.getByText("35.2%")).toBeInTheDocument();
    expect(screen.getByText("9.3%")).toBeInTheDocument();
  });

  it("renders scene map after successful analysis", async () => {
    const result = makePOVResult();
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<POVPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("pov.scenes")).toBeInTheDocument();
    });

    // Scene index is rendered as "pov.scene {number}" (key used by mock)
    // Confidence badges
    expect(screen.getByText("92%")).toBeInTheDocument();
    expect(screen.getByText("67%")).toBeInTheDocument();
    expect(screen.getByText("25%")).toBeInTheDocument();
    // Null character renders as em-dash
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders issues with severity and type badges", async () => {
    const result = makePOVResult();
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<POVPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("pov.headHop")).toBeInTheDocument();
    });

    expect(screen.getByText("pov.knowledgeLeak")).toBeInTheDocument();
    // Quoted text
    expect(screen.getByText(/Bob knew what Alice was thinking/)).toBeInTheDocument();
  });

  it("shows no issues message when issues is empty", async () => {
    const result = makePOVResult({ issues: [] });
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<POVPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("pov.noIssues")).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Expandable issue details
  // -------------------------------------------------------------------------

  it("expands issue to show explanation and suggestion", async () => {
    const user = userEvent.setup();
    const result = makePOVResult();
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<POVPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("pov.headHop")).toBeInTheDocument();
    });

    // Expand first issue — use the accessible name which includes type + location + text
    const issueButton = screen.getByRole("button", {
      name: /pov\.headHop/,
    });
    expect(issueButton).toBeTruthy();
    expect(issueButton).toHaveAttribute("aria-expanded", "false");
    await user.click(issueButton);

    // Should now show explanation and suggestion
    expect(screen.getByText("pov.explanation")).toBeInTheDocument();
    expect(screen.getByText("pov.suggestion")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Error state
  // -------------------------------------------------------------------------

  it("renders error state with retry button when analysis fails", async () => {
    mockMutateAsync = vi.fn().mockRejectedValue(new Error("Network error"));

    render(<POVPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("pov.analysisFailed")).toBeInTheDocument();
    });
    expect(screen.getByText("Network error")).toBeInTheDocument();
    expect(screen.getByText("pov.retry")).toBeInTheDocument();
  });

  it("retry button triggers re-analysis", async () => {
    const user = userEvent.setup();
    mockMutateAsync = vi
      .fn()
      .mockRejectedValueOnce(new Error("fail"))
      .mockResolvedValueOnce(makePOVResult());

    render(<POVPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("pov.retry")).toBeInTheDocument();
    });

    await user.click(screen.getByText("pov.retry"));

    expect(mockMutateAsync).toHaveBeenCalledTimes(2);
  });

  // -------------------------------------------------------------------------
  // Refresh
  // -------------------------------------------------------------------------

  it("refresh button triggers re-analysis in results state", async () => {
    const user = userEvent.setup();
    const result = makePOVResult();
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<POVPanel {...defaultProps} />);

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

    render(<POVPanel {...defaultProps} chapterIds={[]} />);

    expect(mockMutateAsync).not.toHaveBeenCalled();
  });

  // -------------------------------------------------------------------------
  // Edge cases
  // -------------------------------------------------------------------------

  it("handles null pov_character in scene gracefully", async () => {
    const result = makePOVResult({
      scenes: [
        {
          scene_index: 0,
          start_position: 0,
          end_position: 500,
          pov_character: null,
          confidence: 0.1,
        },
      ],
    });
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<POVPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("pov.scenes")).toBeInTheDocument();
    });

    // The em-dash fallback for null character
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("10%")).toBeInTheDocument();
  });

  it("handles empty distribution gracefully", async () => {
    const result = makePOVResult({ pov_distribution: {} });
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<POVPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("pov.analysisType")).toBeInTheDocument();
    });

    // Should not render distribution section
    expect(screen.queryByText("pov.distribution")).not.toBeInTheDocument();
  });

  it("renders all four issue type badges correctly", async () => {
    const result = makePOVResult({
      issues: [
        {
          type: "head_hop",
          location: "Loc 1",
          text: "text1",
          explanation: "exp1",
          suggestion: "sug1",
          severity: "error" as const,
        },
        {
          type: "knowledge_leak",
          location: "Loc 2",
          text: "text2",
          explanation: "exp2",
          suggestion: "sug2",
          severity: "warning" as const,
        },
        {
          type: "emotional_leak",
          location: "Loc 3",
          text: "text3",
          explanation: "exp3",
          suggestion: "sug3",
          severity: "warning" as const,
        },
        {
          type: "physical_impossibility",
          location: "Loc 4",
          text: "text4",
          explanation: "exp4",
          suggestion: "sug4",
          severity: "error" as const,
        },
      ],
    });
    mockMutateAsync = vi.fn().mockResolvedValue(result);

    render(<POVPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("pov.headHop")).toBeInTheDocument();
    });

    expect(screen.getByText("pov.knowledgeLeak")).toBeInTheDocument();
    expect(screen.getByText("pov.emotionalLeak")).toBeInTheDocument();
    expect(screen.getByText("pov.physicalImpossibility")).toBeInTheDocument();
  });
});
