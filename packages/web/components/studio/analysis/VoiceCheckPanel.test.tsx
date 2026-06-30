/**
 * VoiceCheckPanel tests — WRITE-010.
 *
 * Mirrors CharacterVoicePanel.test.tsx (ANAL-008), adapted to the on-demand
 * chapter-scoped design: voice-check does NOT auto-run on mount (the user
 * clicks the Trigger to run it), and it is chapter-scoped (`run(chapterId)`).
 *
 * Mocking strategy:
 * - useCharacterVoiceCheck: state-driven mock (run + {results, error, progress,
 *   flags}). The panel derives its viewState entirely from the hook's return.
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly), so
 * assertions compare against i18n keys (e.g. "voiceCheck.analyzing").
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type { VoiceCheckResult } from "@/lib/api/voice-check-stream";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { VoiceCheckPanel } from "./VoiceCheckPanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockRun: Mock;
let mockState: {
  results: VoiceCheckResult[] | null;
  error: AIErrorResponse | null;
  progress: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  isComplete: boolean;
  isError: boolean;
};

vi.mock("@/lib/hooks/useCharacterVoiceCheck", () => ({
  useCharacterVoiceCheck: () => ({
    run: (...args: unknown[]) => mockRun(...args),
    results: mockState.results,
    error: mockState.error,
    progress: mockState.progress,
    isLoading: mockState.isLoading,
    isStreaming: mockState.isStreaming,
    isComplete: mockState.isComplete,
    isError: mockState.isError,
  }),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeResult(overrides: Partial<VoiceCheckResult> = {}): VoiceCheckResult {
  return {
    character_name: "Elena",
    match_score: 92,
    band: "green",
    match_judgment: "consistent",
    qualitative_sub_score: 90,
    metric_delta_subscore: 94,
    flagged_lines: [
      {
        quote: "\u201cYou won\u2019t forget this.\u201d",
        reason: "Slightly more formal than profile.",
      },
    ],
    has_profile: true,
    n_comparable_metrics: 6,
    ...overrides,
  };
}

const defaultProps = {
  chapterId: "ch-1",
  onClose: vi.fn(),
};

function setState(patch: Partial<typeof mockState>): void {
  mockState = { ...mockState, ...patch };
}

/** Build an AIErrorResponse matching the hook's structured error type. */
function networkError(message: string): AIErrorResponse {
  return {
    kind: "network",
    i18nKey: "aiActions.errorConnection",
    userMessage: message,
    retryable: true,
    cause: new Error(message),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("VoiceCheckPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRun = vi.fn();
    mockState = {
      results: null,
      error: null,
      progress: null,
      isLoading: false,
      isStreaming: false,
      isComplete: false,
      isError: false,
    };
  });

  // -------------------------------------------------------------------------
  // On-demand: does NOT auto-run
  // -------------------------------------------------------------------------

  it("does NOT auto-run analysis on mount (on-demand)", () => {
    render(<VoiceCheckPanel {...defaultProps} />);

    expect(mockRun).not.toHaveBeenCalled();
  });

  it("renders the trigger CTA in the idle state before any run", () => {
    render(<VoiceCheckPanel {...defaultProps} />);

    expect(screen.getByText("voiceCheck.trigger")).toBeInTheDocument();
    expect(screen.getByText("voiceCheck.description")).toBeInTheDocument();
  });

  it("clicking the trigger CTA runs the analysis for the chapter", async () => {
    const user = userEvent.setup();
    render(<VoiceCheckPanel {...defaultProps} />);

    await user.click(screen.getByText("voiceCheck.trigger"));

    expect(mockRun).toHaveBeenCalledWith("ch-1");
    expect(mockRun).toHaveBeenCalledTimes(1);
  });

  it("disables the trigger CTA when no chapter is active", () => {
    render(<VoiceCheckPanel {...defaultProps} chapterId={null} />);

    const button = screen.getByText("voiceCheck.trigger").closest("button")!;
    expect(button.disabled).toBe(true);
  });

  // -------------------------------------------------------------------------
  // Close handlers
  // -------------------------------------------------------------------------

  it("calls onClose when close button (X) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<VoiceCheckPanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[closeButtons.length - 1]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when back button (ArrowLeft) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<VoiceCheckPanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[0]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  it("renders loading state when analysis is in-flight", () => {
    setState({ isLoading: true });
    render(<VoiceCheckPanel {...defaultProps} />);

    expect(screen.getByText("voiceCheck.analyzing")).toBeInTheDocument();
  });

  it("surfaces the progress message while analyzing", () => {
    setState({ isLoading: true, progress: "Found 2 speaking characters" });
    render(<VoiceCheckPanel {...defaultProps} />);

    expect(screen.getByText("Found 2 speaking characters")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Results — per-character rendering
  // -------------------------------------------------------------------------

  it("renders each character name after a successful analysis", async () => {
    setState({
      isComplete: true,
      results: [makeResult({ character_name: "Elena" }), makeResult({ character_name: "Marcus" })],
    });

    render(<VoiceCheckPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Elena")).toBeInTheDocument();
    });
    expect(screen.getByText("Marcus")).toBeInTheDocument();
  });

  it("renders the match score, band, and flagged lines for a scored character", async () => {
    setState({ isComplete: true, results: [makeResult()] });

    render(<VoiceCheckPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "92");
    });
    expect(screen.getByText("voiceCheck.band.green")).toBeInTheDocument();
    expect(screen.getByText("voiceCheck.judgment.consistent")).toBeInTheDocument();
    expect(screen.getByText(/\u201cYou won/)).toBeInTheDocument();
  });

  it("shows no-results message when the result array is empty (no dialogue)", async () => {
    setState({ isComplete: true, results: [] });

    render(<VoiceCheckPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("voiceCheck.noResults")).toBeInTheDocument();
    });
  });

  it("shows a no-profile message for a character without a stored profile", async () => {
    setState({
      isComplete: true,
      results: [
        makeResult({
          character_name: "Marek",
          has_profile: false,
          match_score: null,
          band: null,
          match_judgment: null,
        }),
      ],
    });

    render(<VoiceCheckPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Marek")).toBeInTheDocument();
    });
    expect(screen.getByText("voiceCheck.noVoiceProfile")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Error state
  // -------------------------------------------------------------------------

  it("renders error state with retry button when analysis fails", async () => {
    setState({ isError: true, error: networkError("Network error") });

    render(<VoiceCheckPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("voiceCheck.analysisFailed")).toBeInTheDocument();
    });
    expect(screen.getByText("Network error")).toBeInTheDocument();
    expect(screen.getByText("voiceCheck.retry")).toBeInTheDocument();
  });

  it("retry button triggers re-analysis", async () => {
    const user = userEvent.setup();
    setState({ isError: true, error: networkError("fail") });

    render(<VoiceCheckPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("voiceCheck.retry")).toBeInTheDocument();
    });
    await user.click(screen.getByText("voiceCheck.retry"));

    expect(mockRun).toHaveBeenCalledWith("ch-1");
    expect(mockRun).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // AI disclaimer
  // -------------------------------------------------------------------------

  it("renders the AI disclaimer banner", () => {
    render(<VoiceCheckPanel {...defaultProps} />);

    expect(screen.getByText("voiceCheck.aiDisclaimer")).toBeInTheDocument();
  });
});
