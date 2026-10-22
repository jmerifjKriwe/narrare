/**
 * AuthorVoiceDriftPanel tests — ANAL-009 Phase 2B (Author Voice Drift).
 *
 * Mirrors VoiceDriftPanel.test.tsx (Phase 1), adapted to the singular narrator
 * design: author-voice-drift analyses the whole novel and renders a SINGLE
 * always-visible trend (sparkline + jump markers + classification badge +
 * agent reasoning + per-chapter notes) — no per-character heatmap.
 *
 * Mocking strategy:
 * - useAuthorVoiceDrift: state-driven mock (run + {result, noProfile, error,
 *   progress, flags}). The panel derives its viewState entirely from the hook's
 *   return.
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly), so
 * assertions compare against i18n keys (e.g. "authorVoiceDrift.analyzing").
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type {
  AuthorVoiceDriftNoProfile,
  AuthorVoiceDriftResult,
} from "@/lib/api/author-voice-drift-stream";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { AuthorVoiceDriftPanel } from "./AuthorVoiceDriftPanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockRun: Mock;
let mockState: {
  result: AuthorVoiceDriftResult | null;
  noProfile: AuthorVoiceDriftNoProfile | null;
  error: AIErrorResponse | null;
  progress: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  isComplete: boolean;
  isError: boolean;
};

vi.mock("@/lib/hooks/useAuthorVoiceDrift", () => ({
  useAuthorVoiceDrift: () => ({
    run: (...args: unknown[]) => mockRun(...args),
    result: mockState.result,
    noProfile: mockState.noProfile,
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

function makeResult(overrides: Partial<AuthorVoiceDriftResult> = {}): AuthorVoiceDriftResult {
  return {
    novel_id: "novel-1",
    trend: [
      { chapter_id: "ch-1", match_subscore: 94, per_metric_deltas: {}, band: "stable" },
      {
        chapter_id: "ch-2",
        match_subscore: 71,
        per_metric_deltas: { dialogue_ratio: 0.18 },
        band: "minor",
      },
    ],
    jumps: [
      {
        from_chapter_id: "ch-1",
        to_chapter_id: "ch-2",
        jumped_metrics: ["dialogue_ratio"],
        magnitude: 0.18,
      },
    ],
    overall_match_score: 82,
    overall_band: "minor",
    drift: {
      drift_type: "evolution",
      confidence: 0.72,
      longitudinal_reasons: ["The narrative voice grows more conversational."],
      per_chapter_notes: [{ chapter_id: "ch-2", note: "Shorter sentences." }],
      suggested_attention: ["ch-2"],
    },
    ...overrides,
  };
}

const defaultProps = {
  novelId: "novel-1",
  onClose: vi.fn(),
};

function setState(patch: Partial<typeof mockState>): void {
  mockState = { ...mockState, ...patch };
}

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

describe("AuthorVoiceDriftPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRun = vi.fn();
    mockState = {
      result: null,
      noProfile: null,
      error: null,
      progress: null,
      isLoading: false,
      isStreaming: false,
      isComplete: false,
      isError: false,
    };
  });

  // --- On-demand idle ---

  it("does NOT auto-run analysis on mount (on-demand)", () => {
    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    expect(mockRun).not.toHaveBeenCalled();
  });

  it("renders the Analyze CTA in the idle state", () => {
    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    expect(screen.getByText("authorVoiceDrift.analyze")).toBeInTheDocument();
    expect(screen.getByText("authorVoiceDrift.description")).toBeInTheDocument();
  });

  it("clicking Analyze runs the whole-novel analysis", async () => {
    const user = userEvent.setup();
    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    await user.click(screen.getByText("authorVoiceDrift.analyze"));

    expect(mockRun).toHaveBeenCalledWith("novel-1");
    expect(mockRun).toHaveBeenCalledTimes(1);
  });

  // --- Close handlers ---

  it("calls onClose when close button (X) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<AuthorVoiceDriftPanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[closeButtons.length - 1]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  // --- Loading ---

  it("renders loading state when analysis is in-flight", () => {
    setState({ isLoading: true });
    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    expect(screen.getByText("authorVoiceDrift.analyzing")).toBeInTheDocument();
  });

  it("surfaces the progress message while analyzing", () => {
    setState({ isLoading: true, progress: "Measuring 4 chapters" });
    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    expect(screen.getByText("Measuring 4 chapters")).toBeInTheDocument();
  });

  // --- Results: single narrator trend ---

  it("renders the overall classification badge after a successful analysis", async () => {
    // moderate band → composeClassification surfaces the agent's drift_type
    // (evolution / context / inconsistency); the qualitative call is the
    // valuable signal at this depth (ADR-073 D4).
    setState({ isComplete: true, result: makeResult({ overall_band: "moderate" }) });

    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("authorVoiceDrift.classification.evolution")).toBeInTheDocument();
    });
  });

  it("renders the band-derived classification for a minor band (mildVariation)", async () => {
    setState({ isComplete: true, result: makeResult({ overall_band: "minor" }) });

    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("authorVoiceDrift.classification.mildVariation")).toBeInTheDocument();
    });
  });

  it("renders the shared band legend under the trend (reused voiceDrift.* keys)", async () => {
    setState({ isComplete: true, result: makeResult() });
    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    // The band legend is the shared VoiceDriftBandLegend (same 4 bands, same
    // thresholds, same colour tokens) — it renders the generic voiceDrift.*
    // band keys rather than duplicating them under authorVoiceDrift.*.
    await waitFor(() => {
      expect(screen.getByText("voiceDrift.bandsLabel")).toBeInTheDocument();
    });
    expect(screen.getByText("voiceDrift.band.stable")).toBeInTheDocument();
    expect(screen.getByText("voiceDrift.band.major")).toBeInTheDocument();
  });

  it("renders the agent reasoning quote", async () => {
    setState({ isComplete: true, result: makeResult() });
    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("authorVoiceDrift.agentReasoning")).toBeInTheDocument();
    });
    // VoiceDriftJumpList is reused (generic jump-points key).
    expect(screen.getByText("voiceDrift.jumpPoints")).toBeInTheDocument();
  });

  it("renders the jump points list", async () => {
    setState({ isComplete: true, result: makeResult() });
    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    // VoiceDriftJumpList is reused (renders the generic voiceDrift.* key).
    await waitFor(() => {
      expect(screen.getByText("voiceDrift.jumpPoints")).toBeInTheDocument();
    });
  });

  it("reveals per-chapter notes when the toggle is clicked", async () => {
    const user = userEvent.setup();
    setState({ isComplete: true, result: makeResult() });
    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    await waitFor(() => expect(screen.getByText("authorVoiceDrift.viewNotes")).toBeInTheDocument());
    await user.click(screen.getByText("authorVoiceDrift.viewNotes"));

    expect(screen.getByText("authorVoiceDrift.perChapterNotes")).toBeInTheDocument();
  });

  // --- No-profile state ---

  it("shows the no-profile message when the narrator could not be analysed", async () => {
    setState({
      isComplete: true,
      noProfile: { reason: "no_stored_profile" },
    });

    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("authorVoiceDrift.noProfileTitle")).toBeInTheDocument();
    });
    expect(
      screen.getByText("authorVoiceDrift.noProfileReason.no_stored_profile"),
    ).toBeInTheDocument();
  });

  // --- Error ---

  it("renders error state with retry button when analysis fails", async () => {
    setState({ isError: true, error: networkError("Network error") });

    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("authorVoiceDrift.analysisFailed")).toBeInTheDocument();
    });
    expect(screen.getByText("aiActions.errorConnection")).toBeInTheDocument();
    expect(screen.getByText("authorVoiceDrift.retry")).toBeInTheDocument();
  });

  it("renders the localized error key, not the German userMessage (M05)", () => {
    setState({
      result: null,
      noProfile: null,
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

    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    expect(screen.getByText("aiActions.errorConnection")).toBeDefined();
    expect(screen.queryByText("Verbindung verloren. Prüfe deine Internetverbindung.")).toBeNull();
  });

  it("retry button triggers re-analysis", async () => {
    const user = userEvent.setup();
    setState({ isError: true, error: networkError("fail") });

    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("authorVoiceDrift.retry")).toBeInTheDocument();
    });
    await user.click(screen.getByText("authorVoiceDrift.retry"));

    expect(mockRun).toHaveBeenCalledWith("novel-1");
    expect(mockRun).toHaveBeenCalledTimes(1);
  });

  // --- AI disclaimer ---

  it("renders the AI disclaimer banner", () => {
    render(<AuthorVoiceDriftPanel {...defaultProps} />);

    expect(screen.getByText("authorVoiceDrift.aiDisclaimer")).toBeInTheDocument();
  });
});
