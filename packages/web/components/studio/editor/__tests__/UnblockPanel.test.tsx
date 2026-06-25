/**
 * UnblockPanel tests — Writer's Unblock (WRITE-009).
 *
 * Uses a hoisted useAIOperation mock for controlled state testing:
 * 1. Renders the trigger button when closed
 * 2. Opens the panel on click and shows the input form
 * 3. Shows the loading state while busy
 * 4. Displays suggestion cards (type badge, title, description, connection)
 *    and the Accept action after completion
 * 5. Calls onAccept when a suggestion is accepted
 * 6. Returns to the input form on Dismiss
 * 7. Shows the error state with a retry action
 * 8. Closes the panel on Escape
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UnblockPanel } from "@/components/studio/editor/UnblockPanel";
import type { StorySuggestion } from "@/lib/api/story-suggest-stream";
import type { AIErrorResponse, UseAIOperationReturn } from "@/lib/hooks/use-ai-operation";

// ---------------------------------------------------------------------------
// Hoisted mock data factory
// ---------------------------------------------------------------------------

const {
  mockAiOpRef,
  createIdleReturn,
  createLoadingReturn,
  createCompleteReturn,
  createErrorReturn,
} = vi.hoisted(() => {
  type AiOp = UseAIOperationReturn<unknown>;

  const mockAiOpRef: { current: AiOp } = {
    current: {} as AiOp,
  };

  function base(overrides: Partial<AiOp>): AiOp {
    return {
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
      ...overrides,
    } as AiOp;
  }

  function createIdleReturn(): AiOp {
    return base({ isIdle: true });
  }

  function createLoadingReturn(): AiOp {
    return base({
      state: { status: "loading", result: null, error: null, attemptCount: 1 },
      isIdle: false,
      isLoading: true,
    });
  }

  function createCompleteReturn(suggestions: unknown[]): AiOp {
    return base({
      state: { status: "complete", result: suggestions, error: null, attemptCount: 1 },
      isIdle: false,
      isComplete: true,
    });
  }

  function createErrorReturn(error: AIErrorResponse): AiOp {
    return base({
      state: { status: "error", result: null, error, attemptCount: 1 },
      isIdle: false,
      isError: true,
    });
  }

  return {
    mockAiOpRef,
    createIdleReturn,
    createLoadingReturn,
    createCompleteReturn,
    createErrorReturn,
  };
});

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/hooks/use-ai-operation", () => ({
  useAIOperation: vi.fn(() => mockAiOpRef.current),
}));

vi.mock("@/components/ui/connection-lost-banner", () => ({
  ConnectionLostBanner: ({ onRetry }: { onRetry: () => void }) => (
    <div data-testid="connection-lost-banner">
      Connection Lost
      <button type="button" onClick={onRetry} data-testid="retry-btn">
        Reconnect
      </button>
    </div>
  ),
}));

// next-intl is mocked globally in setupTests.ts: t(key) returns the key.

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const suggestions: StorySuggestion[] = [
  {
    type: "plot_development",
    title: "Introduce a ticking clock",
    description: "Give the protagonist a deadline to raise the stakes.",
    connection: "Connects to the missing motivation in chapter 2.",
  },
  {
    type: "character_moment",
    title: "A quiet confession",
    description: "Let the side character reveal their true fear.",
    connection: "Deepens the emotional arc before the climax.",
  },
];

const defaultProps = {
  novelId: "novel-1",
  chapterId: "ch-1",
  onAccept: vi.fn(),
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setMock(op: UseAIOperationReturn<unknown>): void {
  mockAiOpRef.current = op;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("UnblockPanel", () => {
  it("renders the trigger button when closed", () => {
    setMock(createIdleReturn());
    render(<UnblockPanel {...defaultProps} />);

    expect(screen.getByText("unblock.button")).toBeInTheDocument();
    // Panel is not open yet.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens the panel and shows the input form on click", () => {
    setMock(createIdleReturn());
    render(<UnblockPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("unblock.button"));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText("unblock.title")).toBeInTheDocument();
    // Optional "stuck" textarea + Get Suggestions button.
    expect(screen.getByLabelText("unblock.stuckLabel")).toBeInTheDocument();
    expect(screen.getByText("unblock.getSuggestions")).toBeInTheDocument();
  });

  it("starts the operation when Get Suggestions is clicked", () => {
    const op = createIdleReturn();
    setMock(op);
    render(<UnblockPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("unblock.button"));
    fireEvent.click(screen.getByText("unblock.getSuggestions"));

    expect(op.start).toHaveBeenCalledTimes(1);
  });

  it("shows the loading state while busy", () => {
    const op = createLoadingReturn();
    setMock(op);
    render(<UnblockPanel {...defaultProps} />);

    // Open the panel first (state is loading but panel open flag is internal).
    fireEvent.click(screen.getByText("unblock.button"));

    expect(screen.getByText("unblock.loading")).toBeInTheDocument();
    expect(screen.getByText("aiActions.stop")).toBeInTheDocument();
  });

  it("calls cancel when Stop is clicked", () => {
    const op = createLoadingReturn();
    setMock(op);
    render(<UnblockPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("unblock.button"));
    fireEvent.click(screen.getByText("aiActions.stop"));

    expect(op.cancel).toHaveBeenCalledTimes(1);
  });

  it("displays suggestion cards after completion", () => {
    setMock(createCompleteReturn(suggestions));
    render(<UnblockPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("unblock.button"));

    // Type badge, title, description, connection for each suggestion.
    expect(screen.getByText("unblock.suggestionType.plot_development")).toBeInTheDocument();
    expect(screen.getByText("unblock.suggestionType.character_moment")).toBeInTheDocument();
    expect(screen.getByText("Introduce a ticking clock")).toBeInTheDocument();
    expect(
      screen.getByText("Give the protagonist a deadline to raise the stakes."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Connects to the missing motivation in chapter 2."),
    ).toBeInTheDocument();
    // One Accept button per suggestion + no other aiActions.accept occurrences.
    expect(screen.getAllByText("aiActions.accept")).toHaveLength(2);
    // Dismiss (reject) + Regenerate (newSuggestions) controls.
    expect(screen.getByText("aiActions.reject")).toBeInTheDocument();
    expect(screen.getByText("aiActions.newSuggestions")).toBeInTheDocument();
  });

  it("shows the empty state when no suggestions are returned", () => {
    setMock(createCompleteReturn([]));
    render(<UnblockPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("unblock.button"));

    expect(screen.getByText("unblock.empty")).toBeInTheDocument();
  });

  it("calls onAccept when a suggestion's Accept button is clicked", () => {
    setMock(createCompleteReturn(suggestions));
    const onAccept = vi.fn();
    render(<UnblockPanel {...defaultProps} onAccept={onAccept} />);

    fireEvent.click(screen.getByText("unblock.button"));
    const acceptButtons = screen.getAllByText("aiActions.accept");
    fireEvent.click(acceptButtons[0]);

    expect(onAccept).toHaveBeenCalledTimes(1);
    expect(onAccept).toHaveBeenCalledWith(suggestions[0]);
  });

  it("returns to the input form on Dismiss", () => {
    const op = createCompleteReturn(suggestions);
    setMock(op);
    const { rerender } = render(<UnblockPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("unblock.button"));
    fireEvent.click(screen.getByText("aiActions.reject"));

    // The component delegates the lifecycle transition to the hook (reset).
    expect(op.reset).toHaveBeenCalledTimes(1);

    // Simulate the hook transitioning to idle (as the real hook does on reset),
    // then re-render so the component reflects the new lifecycle state.
    setMock(createIdleReturn());
    rerender(<UnblockPanel {...defaultProps} />);

    // Back to idle: input form visible, results gone.
    expect(screen.getByText("unblock.getSuggestions")).toBeInTheDocument();
    expect(screen.queryByText("Introduce a ticking clock")).not.toBeInTheDocument();
  });

  it("restarts the operation on Regenerate", () => {
    const op = createCompleteReturn(suggestions);
    setMock(op);
    render(<UnblockPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("unblock.button"));
    fireEvent.click(screen.getByText("aiActions.newSuggestions"));

    expect(op.start).toHaveBeenCalledTimes(1);
  });

  it("shows the error state with a retry action", () => {
    const op = createErrorReturn({
      kind: "http",
      status: 500,
      i18nKey: "aiActions.errorConnection",
      userMessage: "Connection lost",
      retryable: true,
      cause: new Error("boom"),
    });
    setMock(op);
    render(<UnblockPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("unblock.button"));

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("aiActions.errorConnection")).toBeInTheDocument();
    fireEvent.click(screen.getByText("aiActions.retry"));
    expect(op.retry).toHaveBeenCalledTimes(1);
  });

  it("closes the panel on Escape", () => {
    setMock(createIdleReturn());
    render(<UnblockPanel {...defaultProps} />);

    fireEvent.click(screen.getByText("unblock.button"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.keyDown(window, { key: "Escape" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
