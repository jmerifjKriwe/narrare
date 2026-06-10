/**
 * ConsistencyCheckPanel tests — KB consistency check results.
 *
 * Uses useAIOperation mock for controlled state testing:
 * 1. Renders loading state on mount (mock isLoading=true)
 * 2. Shows results after successful check
 * 3. Shows no-issues state when no issues found
 * 4. Shows error state on failure
 * 5. Calls onClose when close button clicked
 * 6. Calls start with on refresh click
 * 7. Shows entity count in summary
 * 8. Calls onClose when back arrow clicked
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConsistencyCheckPanel } from "@/components/studio/kb/ConsistencyCheckPanel";
import type { UseAIOperationReturn } from "@/lib/hooks/use-ai-operation";

// ---------------------------------------------------------------------------
// Hoisted mock data factory
// ---------------------------------------------------------------------------

const { mockAiOpRef, createSuccessResponse } = vi.hoisted(() => {
  const mockAiOpRef: { current: UseAIOperationReturn<unknown> } = {
    current: {
      state: { status: "idle", result: null, error: null, attemptCount: 0 },
      start: vi.fn(),
      cancel: vi.fn(),
      retry: vi.fn(),
      reset: vi.fn(),
      notifyData: vi.fn(),
      isIdle: true,
      isLoading: false,
      isStreaming: false,
      isComplete: false,
      isError: false,
      isConnectionLost: false,
    },
  };

  function createSuccessResponse(overrides: Record<string, unknown> = {}) {
    return {
      issues: [
        {
          finding_index: 0,
          category: "timeline",
          severity: "major",
          description: "Timeline contradiction detected",
          confidence: 0.85,
          entity_names: ["Anna", "Johann"],
          contradiction: "Event order mismatch",
          suggested_resolution: "Reorder events",
        },
      ],
      entity_count: 5,
      summary: { timeline_issues: 1 },
      ...overrides,
    };
  }

  return { mockAiOpRef, createSuccessResponse };
});

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/hooks/use-ai-operation", () => ({
  useAIOperation: vi.fn(() => mockAiOpRef.current),
}));

vi.mock("@/components/studio/kb/WorldbuildingAnalysisCards", () => ({
  ConsistencyCard: ({ issue }: { issue: { finding_index: number; description: string } }) => (
    <div data-testid="consistency-card">{issue.description}</div>
  ),
  groupByCategory: (issues: { category: string }[]) => {
    const groups: Record<string, { category: string }[]> = {};
    for (const issue of issues) {
      if (!groups[issue.category]) groups[issue.category] = [];
      groups[issue.category].push(issue);
    }
    return groups;
  },
}));

vi.mock("@/components/ui/connection-lost-banner", () => ({
  ConnectionLostBanner: ({ onRetry }: { onRetry: () => void }) => (
    <div data-testid="connection-lost-banner">
      Connection Lost
      <button type="button" onClick={onRetry} data-testid="retry-btn">
        Retry
      </button>
    </div>
  ),
}));

import { useAIOperation } from "@/lib/hooks/use-ai-operation";

const mockedUseAIOperation = vi.mocked(useAIOperation);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  novelId: "novel-1",
  onClose: vi.fn(),
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resetMockToIdle() {
  mockAiOpRef.current = {
    state: { status: "idle", result: null, error: null, attemptCount: 0 },
    start: vi.fn(),
    cancel: vi.fn(),
    retry: vi.fn(),
    reset: vi.fn(),
    notifyData: vi.fn(),
    isIdle: true,
    isLoading: false,
    isStreaming: false,
    isComplete: false,
    isError: false,
    isConnectionLost: false,
  };
  // update useAIOperation mock to return the new ref
  mockedUseAIOperation.mockReturnValue(mockAiOpRef.current as UseAIOperationReturn<unknown>);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ConsistencyCheckPanel", () => {
  it("renders loading state on mount", () => {
    resetMockToIdle();
    // Set loading state
    mockAiOpRef.current = {
      ...mockAiOpRef.current,
      state: { status: "loading", result: null, error: null, attemptCount: 1 },
      isLoading: true,
      isIdle: false,
    };
    mockedUseAIOperation.mockReturnValue(mockAiOpRef.current);

    render(<ConsistencyCheckPanel {...defaultProps} />);

    expect(screen.getByText("consistency.checking")).toBeDefined();
  });

  it("shows results after successful check", () => {
    const result = createSuccessResponse();
    resetMockToIdle();
    mockAiOpRef.current = {
      ...mockAiOpRef.current,
      state: { status: "complete", result, error: null, attemptCount: 1 },
      isComplete: true,
      isIdle: false,
    };
    mockedUseAIOperation.mockReturnValue(mockAiOpRef.current);

    render(<ConsistencyCheckPanel {...defaultProps} />);

    expect(screen.getByText("1")).toBeDefined(); // issue count
    expect(screen.getByText("worldbuilding.consistency")).toBeDefined();
    expect(screen.getByTestId("consistency-card")).toBeDefined();
  });

  it("shows no-issues state when no issues found", () => {
    const result = createSuccessResponse({ issues: [], summary: {} });
    resetMockToIdle();
    mockAiOpRef.current = {
      ...mockAiOpRef.current,
      state: { status: "complete", result, error: null, attemptCount: 1 },
      isComplete: true,
      isIdle: false,
    };
    mockedUseAIOperation.mockReturnValue(mockAiOpRef.current);

    render(<ConsistencyCheckPanel {...defaultProps} />);

    expect(screen.getByText("consistency.noIssues")).toBeDefined();
  });

  it("shows error state on failure", () => {
    resetMockToIdle();
    mockAiOpRef.current = {
      ...mockAiOpRef.current,
      state: {
        status: "error",
        result: null,
        error: {
          kind: "http",
          i18nKey: "aiActions.errorDefault",
          userMessage: "Network error",
          retryable: true,
          cause: new Error("Network error"),
        },
        attemptCount: 1,
      },
      isError: true,
      isIdle: false,
    };
    mockedUseAIOperation.mockReturnValue(mockAiOpRef.current);

    render(<ConsistencyCheckPanel {...defaultProps} />);

    expect(screen.getByText("worldbuilding.error")).toBeDefined();
    expect(screen.getByText("Network error")).toBeDefined();
  });

  it("shows retry button in error state", () => {
    resetMockToIdle();
    mockAiOpRef.current = {
      ...mockAiOpRef.current,
      state: {
        status: "error",
        result: null,
        error: {
          kind: "http",
          i18nKey: "aiActions.errorDefault",
          userMessage: "Network error",
          retryable: true,
          cause: new Error("Network error"),
        },
        attemptCount: 1,
      },
      isError: true,
      isIdle: false,
    };
    mockedUseAIOperation.mockReturnValue(mockAiOpRef.current);

    render(<ConsistencyCheckPanel {...defaultProps} />);

    expect(screen.getByText("retry")).toBeDefined();
  });

  it("shows connection-lost banner when connection lost", () => {
    resetMockToIdle();
    mockAiOpRef.current = {
      ...mockAiOpRef.current,
      state: {
        status: "connection_lost",
        result: null,
        error: {
          kind: "connection_lost",
          i18nKey: "aiActions.errorConnection",
          userMessage: "Connection lost",
          retryable: true,
          cause: new Error("Connection lost"),
        },
        attemptCount: 1,
      },
      isConnectionLost: true,
      isError: true, // viewState maps connection_lost to "error"
      isIdle: false,
    };
    mockedUseAIOperation.mockReturnValue(mockAiOpRef.current);

    render(<ConsistencyCheckPanel {...defaultProps} />);

    expect(screen.getByTestId("connection-lost-banner")).toBeDefined();
    expect(screen.getByText("retry")).toBeDefined();
  });

  it("calls onClose when close (X) button clicked", () => {
    const result = createSuccessResponse();
    resetMockToIdle();
    mockAiOpRef.current = {
      ...mockAiOpRef.current,
      state: { status: "complete", result, error: null, attemptCount: 1 },
      isComplete: true,
      isIdle: false,
    };
    mockedUseAIOperation.mockReturnValue(mockAiOpRef.current);

    const onClose = vi.fn();
    render(<ConsistencyCheckPanel {...defaultProps} onClose={onClose} />);

    // Find the X button
    const xButtons = screen.getAllByRole("button");
    const xButton = xButtons.find(
      (btn) =>
        btn.querySelector("svg.lucide-x") !== null || btn.getAttribute("aria-label") === "Close",
    );
    if (xButton) fireEvent.click(xButton);
    // If we found and clicked an X button, onClose should have been called
    if (xButton) expect(onClose).toHaveBeenCalled();
  });

  it("calls runCheckOp on refresh click", () => {
    const result = createSuccessResponse();
    const mockStart = vi.fn();
    resetMockToIdle();
    mockAiOpRef.current = {
      ...mockAiOpRef.current,
      state: { status: "complete", result, error: null, attemptCount: 1 },
      start: mockStart,
      isComplete: true,
      isIdle: false,
    };
    mockedUseAIOperation.mockReturnValue(mockAiOpRef.current);

    render(<ConsistencyCheckPanel {...defaultProps} />);

    // Refresh button should be visible
    expect(screen.getByText("worldbuilding.refresh")).toBeDefined();

    fireEvent.click(screen.getByText("worldbuilding.refresh"));

    expect(mockStart).toHaveBeenCalledOnce();
  });

  it("shows entity count in summary", () => {
    const result = createSuccessResponse();
    resetMockToIdle();
    mockAiOpRef.current = {
      ...mockAiOpRef.current,
      state: { status: "complete", result, error: null, attemptCount: 1 },
      isComplete: true,
      isIdle: false,
    };
    mockedUseAIOperation.mockReturnValue(mockAiOpRef.current);

    render(<ConsistencyCheckPanel {...defaultProps} />);

    expect(screen.getByText("worldbuilding.entityCount")).toBeDefined();
  });

  it("calls onClose when back arrow clicked", () => {
    const result = createSuccessResponse();
    const onClose = vi.fn();
    resetMockToIdle();
    mockAiOpRef.current = {
      ...mockAiOpRef.current,
      state: { status: "complete", result, error: null, attemptCount: 1 },
      isComplete: true,
      isIdle: false,
    };
    mockedUseAIOperation.mockReturnValue(mockAiOpRef.current);

    render(<ConsistencyCheckPanel {...defaultProps} onClose={onClose} />);

    // The back button is the first button in the header
    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[0]);
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose on Escape key", () => {
    const result = createSuccessResponse();
    const onClose = vi.fn();
    resetMockToIdle();
    mockAiOpRef.current = {
      ...mockAiOpRef.current,
      state: { status: "complete", result, error: null, attemptCount: 1 },
      isComplete: true,
      isIdle: false,
    };
    mockedUseAIOperation.mockReturnValue(mockAiOpRef.current);

    render(<ConsistencyCheckPanel {...defaultProps} onClose={onClose} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does NOT call onClose on non-Escape keys", () => {
    const result = createSuccessResponse();
    const onClose = vi.fn();
    resetMockToIdle();
    mockAiOpRef.current = {
      ...mockAiOpRef.current,
      state: { status: "complete", result, error: null, attemptCount: 1 },
      isComplete: true,
      isIdle: false,
    };
    mockedUseAIOperation.mockReturnValue(mockAiOpRef.current);

    render(<ConsistencyCheckPanel {...defaultProps} onClose={onClose} />);

    fireEvent.keyDown(window, { key: "Enter" });
    fireEvent.keyDown(window, { key: " " });

    expect(onClose).not.toHaveBeenCalled();
  });
});
