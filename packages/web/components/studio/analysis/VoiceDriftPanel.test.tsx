/**
 * VoiceDriftPanel tests — ANAL-009 Phase 1 (Character Voice Drift).
 *
 * Mirrors VoiceCheckPanel.test.tsx (WRITE-010), adapted to the novel-scoped
 * on-demand design: voice-drift analyses the WHOLE novel and renders the
 * Layout γ heatmap overview + expandable detail.
 *
 * Mocking strategy:
 * - useCharacterVoiceDrift: state-driven mock (run + {results, noProfile,
 *   error, progress, flags}). The panel derives its viewState entirely from the
 *   hook's return.
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly), so
 * assertions compare against i18n keys (e.g. "voiceDrift.analyzing").
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type { VoiceDriftCharacterResult, VoiceDriftNoProfile } from "@/lib/api/voice-drift-stream";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { VoiceDriftPanel } from "./VoiceDriftPanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockRun: Mock;
let mockState: {
  results: VoiceDriftCharacterResult[] | null;
  noProfile: VoiceDriftNoProfile[] | null;
  error: AIErrorResponse | null;
  progress: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  isComplete: boolean;
  isError: boolean;
};

vi.mock("@/lib/hooks/useCharacterVoiceDrift", () => ({
  useCharacterVoiceDrift: () => ({
    run: (...args: unknown[]) => mockRun(...args),
    results: mockState.results,
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

function makeResult(overrides: Partial<VoiceDriftCharacterResult> = {}): VoiceDriftCharacterResult {
  return {
    character_id: "kb-elena",
    character_name: "Elena",
    trend: [
      { chapter_id: "ch-1", match_subscore: 96, per_metric_deltas: {}, band: "stable" },
      {
        chapter_id: "ch-2",
        match_subscore: 78,
        per_metric_deltas: { formality: 0.2 },
        band: "minor",
      },
    ],
    jumps: [
      {
        from_chapter_id: "ch-1",
        to_chapter_id: "ch-2",
        jumped_metrics: ["formality"],
        magnitude: 0.2,
      },
    ],
    overall_match_score: 87,
    overall_band: "minor",
    drift: {
      drift_type: "context",
      confidence: 0.8,
      longitudinal_reasons: ["Scene-dependent variation."],
      per_chapter_notes: [{ chapter_id: "ch-2", note: "Faster pacing." }],
      suggested_attention: [],
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

describe("VoiceDriftPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRun = vi.fn();
    mockState = {
      results: null,
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
    render(<VoiceDriftPanel {...defaultProps} />);

    expect(mockRun).not.toHaveBeenCalled();
  });

  it("renders the Analyze CTA in the idle state", () => {
    render(<VoiceDriftPanel {...defaultProps} />);

    expect(screen.getByText("voiceDrift.analyze")).toBeInTheDocument();
    expect(screen.getByText("voiceDrift.description")).toBeInTheDocument();
  });

  it("clicking Analyze runs the whole-novel analysis", async () => {
    const user = userEvent.setup();
    render(<VoiceDriftPanel {...defaultProps} />);

    await user.click(screen.getByText("voiceDrift.analyze"));

    expect(mockRun).toHaveBeenCalledWith("novel-1");
    expect(mockRun).toHaveBeenCalledTimes(1);
  });

  // --- Close handlers ---

  it("calls onClose when close button (X) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<VoiceDriftPanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[closeButtons.length - 1]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  // --- Loading ---

  it("renders loading state when analysis is in-flight", () => {
    setState({ isLoading: true });
    render(<VoiceDriftPanel {...defaultProps} />);

    expect(screen.getByText("voiceDrift.analyzing")).toBeInTheDocument();
  });

  it("surfaces the progress message while analyzing", () => {
    setState({ isLoading: true, progress: "Profiling 3 characters" });
    render(<VoiceDriftPanel {...defaultProps} />);

    expect(screen.getByText("Profiling 3 characters")).toBeInTheDocument();
  });

  // --- Results: heatmap overview ---

  it("renders each character name after a successful analysis", async () => {
    setState({
      isComplete: true,
      results: [
        makeResult({ character_name: "Elena" }),
        makeResult({ character_name: "Marcus", character_id: "kb-marcus" }),
      ],
    });

    render(<VoiceDriftPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Elena")).toBeInTheDocument();
    });
    expect(screen.getByText("Marcus")).toBeInTheDocument();
  });

  it("renders the band legend under the heatmap", async () => {
    setState({ isComplete: true, results: [makeResult()] });
    render(<VoiceDriftPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("voiceDrift.bandsLabel")).toBeInTheDocument();
    });
    expect(screen.getByText("voiceDrift.band.stable")).toBeInTheDocument();
    expect(screen.getByText("voiceDrift.band.major")).toBeInTheDocument();
  });

  it("expands the detail card when a character row is clicked", async () => {
    const user = userEvent.setup();
    setState({ isComplete: true, results: [makeResult()] });
    render(<VoiceDriftPanel {...defaultProps} />);

    await waitFor(() => expect(screen.getByText("Elena")).toBeInTheDocument());
    // The row toggle button (Elena) — click to expand.
    await user.click(screen.getByRole("button", { name: "voiceDrift.toggleRowAria" }));

    // The agent reasoning quote should now appear in the expanded detail card.
    expect(screen.getByText("voiceDrift.agentReasoning")).toBeInTheDocument();
    expect(screen.getByText("voiceDrift.jumpPoints")).toBeInTheDocument();
  });

  // --- Empty / no-profile states ---

  it("shows the no-profiled-characters empty state when both arrays are empty", async () => {
    setState({ isComplete: true, results: [], noProfile: [] });

    render(<VoiceDriftPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("voiceDrift.noProfiledCharacters")).toBeInTheDocument();
    });
  });

  it("lists skipped characters with their reason when results are empty but noProfile has entries", async () => {
    const noProfile: VoiceDriftNoProfile[] = [
      { character_id: "", character_name: "Marek", reason: "no_stored_profile" },
    ];
    setState({ isComplete: true, results: [], noProfile });

    render(<VoiceDriftPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("voiceDrift.skippedCharacters")).toBeInTheDocument();
    });
    expect(screen.getByText("Marek")).toBeInTheDocument();
    expect(screen.getByText("voiceDrift.noProfileReason.no_stored_profile")).toBeInTheDocument();
  });

  // --- Error ---

  it("renders error state with retry button when analysis fails", async () => {
    setState({ isError: true, error: networkError("Network error") });

    render(<VoiceDriftPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("voiceDrift.analysisFailed")).toBeInTheDocument();
    });
    expect(screen.getByText("Network error")).toBeInTheDocument();
    expect(screen.getByText("voiceDrift.retry")).toBeInTheDocument();
  });

  it("retry button triggers re-analysis", async () => {
    const user = userEvent.setup();
    setState({ isError: true, error: networkError("fail") });

    render(<VoiceDriftPanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("voiceDrift.retry")).toBeInTheDocument();
    });
    await user.click(screen.getByText("voiceDrift.retry"));

    expect(mockRun).toHaveBeenCalledWith("novel-1");
    expect(mockRun).toHaveBeenCalledTimes(1);
  });

  // --- AI disclaimer ---

  it("renders the AI disclaimer banner", () => {
    render(<VoiceDriftPanel {...defaultProps} />);

    expect(screen.getByText("voiceDrift.aiDisclaimer")).toBeInTheDocument();
  });
});
