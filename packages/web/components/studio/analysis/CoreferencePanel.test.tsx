/**
 * CoreferencePanel tests — ANAL-005
 *
 * Tests: loading state, close handler, results (clarity score, summary,
 * pronoun resolutions, character mentions, POV/ambiguous badges), empty
 * states, error with retry, refresh, empty chapterIds.
 *
 * Mocking strategy:
 * - useCoreference: state-driven mock (run + {result,error,flags}). The panel
 *   derives its viewState entirely from the hook's return value, so each test
 *   stages the hook state before rendering.
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly).
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type { CoreferenceResult } from "@/lib/api/coreference-stream";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { CoreferencePanel } from "./CoreferencePanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockRun: Mock;
let mockState: {
  result: CoreferenceResult | null;
  error: AIErrorResponse | null;
  isLoading: boolean;
  isStreaming: boolean;
  isComplete: boolean;
  isError: boolean;
};

vi.mock("@/lib/hooks/useCoreference", () => ({
  useCoreference: () => ({
    run: (...args: unknown[]) => mockRun(...args),
    result: mockState.result,
    error: mockState.error,
    isLoading: mockState.isLoading,
    isStreaming: mockState.isStreaming,
    isComplete: mockState.isComplete,
    isError: mockState.isError,
  }),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeCoreferenceResult(overrides: Partial<CoreferenceResult> = {}): CoreferenceResult {
  return {
    chapter_id: "ch-1",
    clarity_score: 82,
    summary: "Clear and unambiguous referential structure.",
    resolutions: [
      {
        pronoun: "he",
        position: 12,
        referent: "John",
        confidence: 0.85,
        is_ambiguous: false,
      },
      {
        pronoun: "she",
        position: 40,
        referent: "",
        confidence: 0.4,
        is_ambiguous: true,
      },
    ],
    character_mentions: [
      { character_name: "John", mentions: [12, 44, 90], is_pov: true },
      { character_name: "Mary", mentions: [40], is_pov: false },
    ],
    ...overrides,
  };
}

const defaultProps = {
  novelId: "novel-1",
  chapterIds: ["ch-1"],
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

describe("CoreferencePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRun = vi.fn();
    mockState = {
      result: null,
      error: null,
      isLoading: true,
      isStreaming: false,
      isComplete: false,
      isError: false,
    };
  });

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  it("renders loading state on mount when analysis is pending", () => {
    render(<CoreferencePanel {...defaultProps} />);

    expect(screen.getByText("coreference.analyzing")).toBeInTheDocument();
    expect(screen.getByText("coreference.analyzingSubtext")).toBeInTheDocument();
  });

  it("auto-triggers analysis on mount", () => {
    render(<CoreferencePanel {...defaultProps} />);

    expect(mockRun).toHaveBeenCalledWith("ch-1");
    expect(mockRun).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // Close handler
  // -------------------------------------------------------------------------

  it("calls onClose when close button (X) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(<CoreferencePanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[closeButtons.length - 1]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when back button (ArrowLeft) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(<CoreferencePanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[0]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  // -------------------------------------------------------------------------
  // Results state
  // -------------------------------------------------------------------------

  it("renders clarity score after successful analysis", async () => {
    setState({ isComplete: true, isLoading: false, result: makeCoreferenceResult() });

    render(<CoreferencePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("coreference.clarityScore")).toBeInTheDocument();
    });

    expect(screen.getByText("82")).toBeInTheDocument();
  });

  it("renders summary after successful analysis", async () => {
    setState({
      isComplete: true,
      isLoading: false,
      result: makeCoreferenceResult({ summary: "Referents are clear throughout." }),
    });

    render(<CoreferencePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("coreference.summary")).toBeInTheDocument();
    });

    expect(screen.getByText("Referents are clear throughout.")).toBeInTheDocument();
  });

  it("renders pronoun resolutions with confidence", async () => {
    setState({ isComplete: true, isLoading: false, result: makeCoreferenceResult() });

    render(<CoreferencePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("coreference.resolutions")).toBeInTheDocument();
    });

    expect(screen.getByText("he")).toBeInTheDocument();
    // "John" appears both as a resolution referent and a character mention
    expect(screen.getAllByText("John").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it("renders ambiguous badge for ambiguous resolutions", async () => {
    setState({ isComplete: true, isLoading: false, result: makeCoreferenceResult() });

    render(<CoreferencePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("coreference.ambiguous")).toBeInTheDocument();
    });
  });

  it("renders character mentions with POV badge", async () => {
    setState({ isComplete: true, isLoading: false, result: makeCoreferenceResult() });

    render(<CoreferencePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("coreference.characterMentions")).toBeInTheDocument();
    });

    expect(screen.getByText("coreference.pov")).toBeInTheDocument();
    // Both characters render the mentions-count key
    expect(screen.getAllByText("coreference.mentions").length).toBe(2);
  });

  it("shows no-results message when resolutions is empty", async () => {
    setState({
      isComplete: true,
      isLoading: false,
      result: makeCoreferenceResult({ resolutions: [] }),
    });

    render(<CoreferencePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("coreference.noResults")).toBeInTheDocument();
    });
  });

  it("shows no-mentions message when character_mentions is empty", async () => {
    setState({
      isComplete: true,
      isLoading: false,
      result: makeCoreferenceResult({ character_mentions: [] }),
    });

    render(<CoreferencePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("coreference.noMentions")).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Error state
  // -------------------------------------------------------------------------

  it("renders error state with retry button when analysis fails", async () => {
    setState({ isError: true, isLoading: false, error: networkError("Network error") });

    render(<CoreferencePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("coreference.analysisFailed")).toBeInTheDocument();
    });
    expect(screen.getByText("aiActions.errorConnection")).toBeInTheDocument();
    expect(screen.getByText("retry")).toBeInTheDocument();
  });

  it("renders the localized error key, not the German userMessage (M05)", () => {
    setState({
      result: null,
      error: {
        kind: "stream",
        i18nKey: "aiActions.errorConnection",
        userMessage: "Verbindung verloren. Prüfe deine Internetverbindung.",
        retryable: true,
        cause: new Error("stream death"),
      },
      isLoading: false,
      isStreaming: false,
      isComplete: false,
      isError: true,
    });

    render(<CoreferencePanel {...defaultProps} />);

    expect(screen.getByText("aiActions.errorConnection")).toBeDefined();
    expect(screen.queryByText("Verbindung verloren. Prüfe deine Internetverbindung.")).toBeNull();
  });

  it("retry button triggers re-analysis", async () => {
    const user = userEvent.setup();
    setState({ isError: true, isLoading: false, error: networkError("fail") });

    render(<CoreferencePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("retry")).toBeInTheDocument();
    });

    await user.click(screen.getByText("retry"));

    // Once on mount, once on retry
    expect(mockRun).toHaveBeenCalledTimes(2);
  });

  // -------------------------------------------------------------------------
  // Refresh
  // -------------------------------------------------------------------------

  it("refresh button triggers re-analysis in results state", async () => {
    const user = userEvent.setup();
    setState({ isComplete: true, isLoading: false, result: makeCoreferenceResult() });

    render(<CoreferencePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("refresh")).toBeInTheDocument();
    });

    await user.click(screen.getByText("refresh"));

    expect(mockRun).toHaveBeenCalledTimes(2);
  });

  // -------------------------------------------------------------------------
  // Empty chapterIds
  // -------------------------------------------------------------------------

  it("handles empty chapterIds gracefully without triggering analysis", () => {
    render(<CoreferencePanel {...defaultProps} chapterIds={[]} />);

    expect(mockRun).not.toHaveBeenCalled();
    // No loading state when there is no chapter
    expect(screen.queryByText("coreference.analyzing")).not.toBeInTheDocument();
  });
});
