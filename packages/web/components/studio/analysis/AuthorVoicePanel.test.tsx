/**
 * AuthorVoicePanel tests — ANAL-007
 *
 * Mirrors CharacterVoicePanel.test.tsx (ANAL-008) and VoiceDriftPanel.test.tsx
 * (on-demand pattern). Tests: idle (Analyze CTA + chapter multi-select), auto
 * "all chapters" default, <3-chapter soft warning, loading, results (descriptive
 * + examples + advanced-metrics toggle), empty profile, error + retry,
 * re-analyze, and close handlers.
 *
 * Mocking strategy:
 * - useAuthorVoice: state-driven mock (run + {result,error,flags}). The panel
 *   derives its viewState entirely from the hook's return value.
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly), so
 * assertions compare against i18n keys (e.g. "authorVoice.analyzing").
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type { AuthorVoiceProfile, AuthorVoiceResult } from "@/lib/api/author-voice-stream";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import type { ChapterSummary } from "@/types";
import { AuthorVoicePanel } from "./AuthorVoicePanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockRun: Mock;
let mockReset: Mock;
let mockState: {
  result: AuthorVoiceResult | null;
  error: AIErrorResponse | null;
  isLoading: boolean;
  isStreaming: boolean;
  isComplete: boolean;
  isError: boolean;
};

vi.mock("@/lib/hooks/useAuthorVoice", () => ({
  useAuthorVoice: () => ({
    run: (...args: unknown[]) => mockRun(...args),
    reset: (...args: unknown[]) => mockReset(...args),
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

function makeProfile(overrides: Partial<AuthorVoiceProfile> = {}): AuthorVoiceProfile {
  return {
    voice_analysis: {
      formality: 0.72,
      vocabulary_level: "moderate",
      sentence_profile: "varied",
      emotional_range: "expressive",
      cultural_regional_markers: "Formal register with nautical idioms",
      voice_examples: ["The harbour bell tolled."],
      voice_metrics: {
        avg_sentence_length: 14.2,
        sentence_length_std: 5.1,
        type_token_ratio: 0.71,
        avg_syllables_per_word: 1.4,
        contraction_rate: 0.08,
        punctuation_profile: { em_dash: 0.02 },
      },
    },
    author_examples: ["The wind carried salt and memory.", "Dawn broke slow and grey."],
    author_metrics: {
      dialogue_ratio: 0.34,
      description_density: 0.18,
      action_introspection_ratio: 0.55,
      metaphor_density: 0.02,
    },
    updated_at: "2026-07-27T10:00:00Z",
    is_fresh: true,
    ...overrides,
  };
}

function makeResult(overrides: Partial<AuthorVoiceResult> = {}): AuthorVoiceResult {
  return { novel_id: "novel-1", profile: makeProfile(), ...overrides };
}

function makeChapter(overrides: Partial<ChapterSummary> = {}): ChapterSummary {
  return {
    id: "ch-1",
    novel_id: "novel-1",
    volume_id: null,
    title: "Chapter 1",
    position: 1,
    word_count: 3000,
    status: "draft",
    updated_at: "2026-07-27T10:00:00Z",
    ...overrides,
  };
}

function makeChapters(n: number): ChapterSummary[] {
  return Array.from({ length: n }, (_, i) =>
    makeChapter({ id: `ch-${i + 1}`, title: `Chapter ${i + 1}`, position: i + 1 }),
  );
}

const defaultProps = {
  novelId: "novel-1",
  chapters: makeChapters(4),
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

describe("AuthorVoicePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRun = vi.fn();
    mockReset = vi.fn();
    mockState = {
      result: null,
      error: null,
      isLoading: false,
      isStreaming: false,
      isComplete: false,
      isError: false,
    };
  });

  // -------------------------------------------------------------------------
  // Idle — Analyze CTA + chapter multi-select
  // -------------------------------------------------------------------------

  it("renders idle state with Analyze Voice CTA on mount", () => {
    render(<AuthorVoicePanel {...defaultProps} />);

    expect(screen.getByText("authorVoice.idleTitle")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "authorVoice.analyze" })).toBeInTheDocument();
  });

  it("does not auto-run analysis on mount (on-demand, like VoiceDriftPanel)", () => {
    render(<AuthorVoicePanel {...defaultProps} />);

    expect(mockRun).not.toHaveBeenCalled();
  });

  it("defaults to selecting all chapters", () => {
    render(<AuthorVoicePanel {...defaultProps} />);

    // All 4 chapter checkboxes are checked by default. Native checkboxes
    // expose state via the `checked` IDL property (jest-dom's toBeChecked),
    // NOT via an explicit aria-checked DOM attribute — native checkbox
    // elements correctly omit the redundant aria-checked per the ARIA spec.
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(4);
    for (const checkbox of checkboxes) {
      expect(checkbox).toBeChecked();
    }
  });

  it("clicking Analyze Voice runs analysis with all chapter ids when all are selected", async () => {
    const user = userEvent.setup();
    render(<AuthorVoicePanel {...defaultProps} />);

    await user.click(screen.getByRole("button", { name: "authorVoice.analyze" }));

    expect(mockRun).toHaveBeenCalledWith("novel-1", null);
  });

  it("clicking Analyze Voice runs with the explicit subset when chapters are deselected", async () => {
    const user = userEvent.setup();
    render(<AuthorVoicePanel {...defaultProps} />);

    // Deselect ch-2 and ch-4 — leaves ch-1 and ch-3.
    await user.click(screen.getByLabelText("Chapter 2"));
    await user.click(screen.getByLabelText("Chapter 4"));

    await user.click(screen.getByRole("button", { name: "authorVoice.analyze" }));

    expect(mockRun).toHaveBeenCalledWith("novel-1", ["ch-1", "ch-3"]);
  });

  it("shows a soft warning when fewer than 3 chapters are selected (does not block)", async () => {
    const user = userEvent.setup();
    render(<AuthorVoicePanel {...defaultProps} />);

    // Deselect down to 2 chapters.
    await user.click(screen.getByLabelText("Chapter 3"));
    await user.click(screen.getByLabelText("Chapter 4"));

    expect(screen.getByText("authorVoice.minChaptersWarning")).toBeInTheDocument();
    // The button is still enabled — the warning is soft (does not block).
    expect(screen.getByRole("button", { name: "authorVoice.analyze" })).toBeEnabled();
  });

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  it("renders loading state when analysis is in flight", () => {
    setState({ isLoading: true });
    render(<AuthorVoicePanel {...defaultProps} />);

    expect(screen.getByText("authorVoice.analyzing")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Results — descriptive + examples + advanced metrics
  // -------------------------------------------------------------------------

  it("renders the descriptive profile fields after a successful analysis", async () => {
    setState({ isComplete: true, result: makeResult() });
    render(<AuthorVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("authorVoice.descriptiveSummary")).toBeInTheDocument();
    });

    expect(screen.getByText("authorVoice.vocabularyLevel")).toBeInTheDocument();
    expect(screen.getByText("authorVoice.sentenceProfile")).toBeInTheDocument();
    expect(screen.getByText("authorVoice.emotionalRange")).toBeInTheDocument();
    expect(screen.getByText("authorVoice.culturalRegionalMarkers")).toBeInTheDocument();
  });

  it("renders formality as a percentage of the persisted value", async () => {
    setState({ isComplete: true, result: makeResult() });
    render(<AuthorVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("72%")).toBeInTheDocument();
    });
  });

  it("renders the categorical profile values verbatim", async () => {
    setState({ isComplete: true, result: makeResult() });
    render(<AuthorVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("moderate")).toBeInTheDocument();
    });

    expect(screen.getByText("varied")).toBeInTheDocument();
    expect(screen.getByText("expressive")).toBeInTheDocument();
  });

  it("renders curated author example passages", async () => {
    setState({ isComplete: true, result: makeResult() });
    render(<AuthorVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("authorVoice.authorExamples")).toBeInTheDocument();
    });

    expect(screen.getByText(/The wind carried salt/)).toBeInTheDocument();
    expect(screen.getByText(/Dawn broke slow/)).toBeInTheDocument();
  });

  it("renders the freshness indicator and last-analyzed timestamp", async () => {
    setState({ isComplete: true, result: makeResult() });
    render(<AuthorVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText(/authorVoice\.lastAnalyzed/)).toBeInTheDocument();
    });
  });

  it("hides the advanced metrics by default and reveals them on toggle", async () => {
    const user = userEvent.setup();
    setState({ isComplete: true, result: makeResult() });
    render(<AuthorVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("authorVoice.advancedMetrics")).toBeInTheDocument();
    });

    // Author-specific prose metrics are hidden until expanded.
    expect(screen.queryByText("authorVoice.dialogueRatio")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "authorVoice.advancedMetricsShow" }));

    expect(screen.getByText("authorVoice.dialogueRatio")).toBeInTheDocument();
    expect(screen.getByText("authorVoice.descriptionDensity")).toBeInTheDocument();
    expect(screen.getByText("authorVoice.metricsCaveat")).toBeInTheDocument();
  });

  it("shows no-results message when the profile is null", async () => {
    setState({ isComplete: true, result: makeResult({ profile: null }) });
    render(<AuthorVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("authorVoice.noProfile")).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Error state
  // -------------------------------------------------------------------------

  it("renders error state with retry button when analysis fails", async () => {
    setState({ isError: true, error: networkError("Network error") });
    render(<AuthorVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("authorVoice.analysisFailed")).toBeInTheDocument();
    });

    expect(screen.getByText("aiActions.errorConnection")).toBeInTheDocument();
    expect(screen.getByText("authorVoice.retry")).toBeInTheDocument();
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

    render(<AuthorVoicePanel {...defaultProps} />);

    expect(screen.getByText("aiActions.errorConnection")).toBeDefined();
    expect(screen.queryByText("Verbindung verloren. Prüfe deine Internetverbindung.")).toBeNull();
  });

  it("retry button triggers re-analysis", async () => {
    const user = userEvent.setup();
    setState({ isError: true, error: networkError("fail") });

    render(<AuthorVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("authorVoice.retry")).toBeInTheDocument();
    });

    await user.click(screen.getByText("authorVoice.retry"));

    expect(mockRun).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // Re-analyze from results
  // -------------------------------------------------------------------------

  it("Re-analyze button in results header triggers a new analysis", async () => {
    const user = userEvent.setup();
    setState({ isComplete: true, result: makeResult() });

    render(<AuthorVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("authorVoice.reanalyze")).toBeInTheDocument();
    });

    await user.click(screen.getByText("authorVoice.reanalyze"));

    expect(mockRun).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // Close handlers
  // -------------------------------------------------------------------------

  it("calls onClose when close button (X) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(<AuthorVoicePanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[closeButtons.length - 1]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when back button (ArrowLeft) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(<AuthorVoicePanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[0]);

    expect(onClose).toHaveBeenCalledOnce();
  });
});
