/**
 * ConsistencyPanel tests — CONS-001
 *
 * Tests: loading state, close handler, severity badges, scope selector,
 * error with retry, elapsed timer during loading.
 *
 * Mocking strategy:
 * - useConsistencyStream: controlled mock for all lifecycle states
 * - useEditorStore: mock selectors
 * - ConsistencyIssueList: mock as stub (tested separately)
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly).
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ConsistencyResponse } from "@/lib/api/analysis";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { ConsistencyPanel } from "./ConsistencyPanel";

// ---------------------------------------------------------------------------
// Mock state — shared variable that the mock hook factory reads on each call
// ---------------------------------------------------------------------------

let mockHook: Record<string, unknown> = {};

vi.mock("@/lib/hooks/useConsistencyStream", () => ({
  useConsistencyStream: () => ({
    // Default idle state
    run: vi.fn(),
    cancel: vi.fn(),
    retry: vi.fn(),
    reset: vi.fn(),
    progress: null,
    issues: [],
    result: null,
    error: null,
    isIdle: true,
    isLoading: false,
    isStreaming: false,
    isComplete: false,
    isError: false,
    isConnectionLost: false,
    state: { status: "idle", result: null, error: null, attemptCount: 0 },
    // Per-test overrides
    ...mockHook,
  }),
}));

const mockSetConsistencyResult = vi.fn();
const mockSetConsistencyLoading = vi.fn();

vi.mock("@/lib/stores/editorStore", () => ({
  useEditorStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      setConsistencyResult: mockSetConsistencyResult,
      setConsistencyLoading: mockSetConsistencyLoading,
      activeChapterId: "ch-1",
    }),
}));

vi.mock("./ConsistencyIssueList", () => ({
  ConsistencyIssueList: ({ issues }: { issues: unknown[] }) => (
    <div data-testid="issue-list">{issues.length} issues</div>
  ),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeConsistencyResponse(
  overrides: Partial<ConsistencyResponse> = {},
): ConsistencyResponse {
  return {
    novel_id: "novel-1",
    chapter_ids: ["ch-1"],
    check_types: ["character", "timeline", "world", "plot"],
    issues: [
      {
        check_type: "character",
        severity: "error",
        description: "Character eye color changes between chapters",
        locations: ["Chapter 1", "Chapter 3"],
        conflicting_facts: ["Blue eyes (Ch 1)", "Brown eyes (Ch 3)"],
        suggestion: "Fix eye color to be consistent",
        confidence: 0.9,
      },
      {
        check_type: "timeline",
        severity: "warning",
        description: "Timeline gap in chapter sequence",
        locations: ["Chapter 2"],
        conflicting_facts: ["Tuesday morning → Thursday afternoon"],
        suggestion: null,
        confidence: 0.7,
      },
      {
        check_type: "world",
        severity: "info",
        description: "New location not in world map",
        locations: ["Chapter 4"],
        conflicting_facts: [],
        suggestion: "Consider adding to KB",
        confidence: 0.5,
      },
    ],
    error_count: 1,
    warning_count: 1,
    info_count: 1,
    total_issues: 3,
    overall_assessment: "Mostly consistent with minor issues.",
    analyzed_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

const defaultProps = {
  novelId: "novel-1",
  chapterIds: ["ch-1", "ch-2"],
  onClose: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ConsistencyPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockHook = {};
  });

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  it("renders loading state on mount", () => {
    // Simulate loading: the hook returns isLoading=true on first render
    mockHook = {
      isIdle: false,
      isLoading: true,
      isComplete: false,
      isError: false,
    };

    render(<ConsistencyPanel {...defaultProps} />);

    // Loading state shows elapsed time text
    expect(screen.getByText(/consistency.loadingElapsed/)).toBeInTheDocument();
  });

  it("calls setConsistencyLoading(true) during loading", () => {
    mockHook = {
      isIdle: false,
      isLoading: true,
    };

    render(<ConsistencyPanel {...defaultProps} />);

    expect(mockSetConsistencyLoading).toHaveBeenCalledWith(true);
  });

  it("calls run on mount", () => {
    // The run function is called via runCheck on mount when idle
    // We need to capture the run mock to verify it was called
    const runMock = vi.fn();
    mockHook = {
      isIdle: true,
      isLoading: false,
      run: runMock,
    };

    render(<ConsistencyPanel {...defaultProps} />);

    expect(runMock).toHaveBeenCalledTimes(1);
    expect(runMock).toHaveBeenCalledWith(
      "novel-1",
      expect.objectContaining({
        chapter_ids: ["ch-1", "ch-2"],
        check_types: ["character", "timeline", "world", "plot"],
        include_kb: true,
      }),
    );
  });

  // -------------------------------------------------------------------------
  // Close handler
  // -------------------------------------------------------------------------

  it("calls onClose when close button is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    mockHook = {
      isIdle: false,
      isLoading: true,
    };

    render(<ConsistencyPanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[closeButtons.length - 1]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  // -------------------------------------------------------------------------
  // Results state — severity badges
  // -------------------------------------------------------------------------

  it("renders severity badges with correct counts in results", async () => {
    const result = makeConsistencyResponse();
    mockHook = {
      isIdle: false,
      isComplete: true,
      result,
      state: { status: "complete", result, error: null, attemptCount: 1 },
    };

    render(<ConsistencyPanel {...defaultProps} />);

    // Wait for results state
    await waitFor(() => {
      expect(screen.getByText("consistency.overallAssessment")).toBeInTheDocument();
    });

    // Severity badges render counts
    expect(screen.getByText("consistency.severity.error")).toBeInTheDocument();
    expect(screen.getByText("consistency.severity.warning")).toBeInTheDocument();
    expect(screen.getByText("consistency.severity.info")).toBeInTheDocument();
  });

  it("renders overall assessment in results", async () => {
    const result = makeConsistencyResponse();
    mockHook = {
      isIdle: false,
      isComplete: true,
      result,
      state: { status: "complete", result, error: null, attemptCount: 1 },
    };

    render(<ConsistencyPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Mostly consistent with minor issues.")).toBeInTheDocument();
    });
  });

  it("stores result in editor store on success", async () => {
    const result = makeConsistencyResponse();
    mockHook = {
      isIdle: false,
      isComplete: true,
      result,
      state: { status: "complete", result, error: null, attemptCount: 1 },
    };

    render(<ConsistencyPanel {...defaultProps} />);

    await waitFor(() => {
      expect(mockSetConsistencyResult).toHaveBeenCalledWith(result);
    });
  });

  // -------------------------------------------------------------------------
  // Scope selector
  // -------------------------------------------------------------------------

  it("renders scope selector with three options when not loading", async () => {
    const result = makeConsistencyResponse();
    mockHook = {
      isIdle: false,
      isComplete: true,
      result,
      state: { status: "complete", result, error: null, attemptCount: 1 },
    };

    render(<ConsistencyPanel {...defaultProps} />);

    // Wait for results state (scope selector is hidden during loading)
    await waitFor(() => {
      expect(screen.getByText("consistency.overallAssessment")).toBeInTheDocument();
    });

    // Scope selector should now be visible
    expect(screen.getByText("consistency.scope.label")).toBeInTheDocument();
    expect(screen.getByText("consistency.scope.current")).toBeInTheDocument();
    expect(screen.getByText("consistency.scope.selected")).toBeInTheDocument();
    expect(screen.getByText("consistency.scope.all")).toBeInTheDocument();
  });

  it("scope selector default is 'selected' (aria-pressed)", async () => {
    const result = makeConsistencyResponse();
    mockHook = {
      isIdle: false,
      isComplete: true,
      result,
      state: { status: "complete", result, error: null, attemptCount: 1 },
    };

    render(<ConsistencyPanel {...defaultProps} />);

    // Wait for results state
    await waitFor(() => {
      expect(screen.getByText("consistency.overallAssessment")).toBeInTheDocument();
    });

    const selectedButton = screen.getByText("consistency.scope.selected").closest("button");
    expect(selectedButton).toHaveAttribute("aria-pressed", "true");
    const currentButton = screen.getByText("consistency.scope.current").closest("button");
    expect(currentButton).toHaveAttribute("aria-pressed", "false");
  });

  // -------------------------------------------------------------------------
  // Error state
  // -------------------------------------------------------------------------

  it("renders error state with retry button when check fails", async () => {
    const error: AIErrorResponse = {
      kind: "network",
      i18nKey: "aiActions.errorConnection",
      userMessage: "Server error",
      retryable: true,
      cause: new Error("Server error"),
    };
    mockHook = {
      isIdle: false,
      isError: true,
      error,
      state: { status: "error", result: null, error, attemptCount: 1 },
    };

    render(<ConsistencyPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("aiActions.errorConnection")).toBeInTheDocument();
    });
    expect(screen.getByText("error")).toBeInTheDocument();
    expect(screen.getByText("aiActions.retry")).toBeInTheDocument();
  });

  it("renders the localized error key, not the German userMessage (M05)", () => {
    const error: AIErrorResponse = {
      kind: "stream",
      i18nKey: "aiActions.errorConnection",
      userMessage: "Verbindung verloren. Prüfe deine Internetverbindung.",
      retryable: true,
      cause: new Error("stream death"),
    };
    mockHook = {
      isIdle: false,
      isError: true,
      error,
      state: { status: "error", result: null, error, attemptCount: 1 },
    };

    render(<ConsistencyPanel {...defaultProps} />);

    expect(screen.getByText("aiActions.errorConnection")).toBeDefined();
    expect(screen.queryByText("Verbindung verloren. Prüfe deine Internetverbindung.")).toBeNull();
  });

  it("retry button triggers re-check", async () => {
    const user = userEvent.setup();
    const runMock = vi.fn();
    const error = { userMessage: "fail" };
    mockHook = {
      isIdle: false,
      isError: true,
      error,
      run: runMock,
      state: { status: "error", result: null, error, attemptCount: 1 },
    };

    render(<ConsistencyPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("aiActions.retry")).toBeInTheDocument();
    });

    await user.click(screen.getByText("aiActions.retry"));

    // Retry calls runCheck, which calls run
    expect(runMock).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // Elapsed timer
  // -------------------------------------------------------------------------

  it("loading state shows elapsed timer text", () => {
    mockHook = {
      isIdle: false,
      isLoading: true,
    };

    render(<ConsistencyPanel {...defaultProps} />);

    // The elapsed timer shows "consistency.loadingElapsed" with seconds param
    expect(screen.getByText(/consistency.loadingElapsed/)).toBeInTheDocument();
    // Also shows progress step
    expect(screen.getByText("consistency.progress.collecting")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Refresh
  // -------------------------------------------------------------------------

  it("refresh button triggers re-check in results state", async () => {
    const user = userEvent.setup();
    const runMock = vi.fn();
    const result = makeConsistencyResponse();
    mockHook = {
      isIdle: false,
      isComplete: true,
      result,
      run: runMock,
      state: { status: "complete", result, error: null, attemptCount: 1 },
    };

    render(<ConsistencyPanel {...defaultProps} />);

    await waitFor(() => {
      // The refresh button in the header
      const refreshButtons = screen.getAllByText("refresh");
      expect(refreshButtons.length).toBeGreaterThan(0);
    });

    // Click the refresh button (in header, not footer)
    const refreshButtons = screen.getAllByText("refresh");
    await user.click(refreshButtons[0]);

    // Refresh triggers runCheck, which calls run
    expect(runMock).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // Scope selector hidden during loading
  // -------------------------------------------------------------------------

  it("hides scope selector during loading state", () => {
    mockHook = {
      isIdle: false,
      isLoading: true,
    };

    render(<ConsistencyPanel {...defaultProps} />);

    // The scope label should NOT be present during loading
    expect(screen.queryByText("consistency.scope.label")).not.toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Progress display (streaming)
  // -------------------------------------------------------------------------

  it("shows progress message during loading when available", () => {
    mockHook = {
      isIdle: false,
      isLoading: true,
      progress: {
        stage: "checking_consistency",
        status: "progress",
        progress: 0.5,
        message: "Checking timeline consistency…",
        factsExtracted: null,
        issuesFound: 2,
      },
    };

    render(<ConsistencyPanel {...defaultProps} />);

    expect(screen.getByText("Checking timeline consistency…")).toBeInTheDocument();
    // Progress percentage should be shown
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("shows cancel button during loading", () => {
    const cancelMock = vi.fn();
    mockHook = {
      isIdle: false,
      isLoading: true,
      cancel: cancelMock,
    };

    render(<ConsistencyPanel {...defaultProps} />);

    expect(screen.getByText("aiActions.stop")).toBeInTheDocument();
  });
});
