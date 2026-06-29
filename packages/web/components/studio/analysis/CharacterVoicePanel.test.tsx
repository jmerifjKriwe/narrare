/**
 * CharacterVoicePanel tests — ANAL-008
 *
 * Mirrors CoreferencePanel.test.tsx (ANAL-005). Tests: loading state, auto-run,
 * close handlers, per-character results (every persisted metric field, voice
 * examples), the display-only `distinctiveness_notes` (labelled per-run /
 * not-stored), empty results, missing voice_analysis, error + retry, refresh,
 * and empty-chapterIds guard.
 *
 * Mocking strategy:
 * - useCharacterVoice: state-driven mock (run + {results,error,flags}). The
 *   panel derives its viewState entirely from the hook's return value.
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly), so
 * assertions compare against i18n keys (e.g. "characterVoice.analyzing").
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type { CharacterVoiceResult, VoiceAnalysis } from "@/lib/api/character-voice-stream";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { CharacterVoicePanel } from "./CharacterVoicePanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockRun: Mock;
let mockState: {
  results: CharacterVoiceResult[] | null;
  error: AIErrorResponse | null;
  isLoading: boolean;
  isStreaming: boolean;
  isComplete: boolean;
  isError: boolean;
};

vi.mock("@/lib/hooks/useCharacterVoice", () => ({
  useCharacterVoice: () => ({
    run: (...args: unknown[]) => mockRun(...args),
    results: mockState.results,
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

function makeVoiceAnalysis(overrides: Partial<VoiceAnalysis> = {}): VoiceAnalysis {
  return {
    formality: 0.72,
    vocabulary_level: "moderate",
    sentence_profile: "varied",
    emotional_range: "expressive",
    cultural_regional_markers: "Formal register with nautical idioms",
    voice_examples: [
      "\u201cBy the stars, you\u2019re stubborn.\u201d",
      "\u201cAye, captain.\u201d",
    ],
    ...overrides,
  };
}

function makeCharacterVoiceResult(
  overrides: Partial<CharacterVoiceResult> = {},
): CharacterVoiceResult {
  return {
    character_name: "Elena",
    voice_analysis: makeVoiceAnalysis(),
    distinctiveness_notes:
      "Elena\u2019s nautical idioms set her apart from Marcus\u2019s terse brevity.",
    kb_entry_id: "kb-1",
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

describe("CharacterVoicePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRun = vi.fn();
    mockState = {
      results: null,
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
    render(<CharacterVoicePanel {...defaultProps} />);

    expect(screen.getByText("characterVoice.analyzing")).toBeInTheDocument();
    expect(screen.getByText("characterVoice.analyzingSubtext")).toBeInTheDocument();
  });

  it("auto-triggers analysis on mount with novelId + active chapter", () => {
    render(<CharacterVoicePanel {...defaultProps} />);

    expect(mockRun).toHaveBeenCalledWith("novel-1", ["ch-1"]);
    expect(mockRun).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // Close handlers
  // -------------------------------------------------------------------------

  it("calls onClose when close button (X) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(<CharacterVoicePanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[closeButtons.length - 1]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when back button (ArrowLeft) is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(<CharacterVoicePanel {...defaultProps} onClose={onClose} />);

    const closeButtons = screen.getAllByLabelText("close");
    await user.click(closeButtons[0]);

    expect(onClose).toHaveBeenCalledOnce();
  });

  // -------------------------------------------------------------------------
  // Results — per-character rendering
  // -------------------------------------------------------------------------

  it("renders each character name after a successful analysis", async () => {
    setState({
      isComplete: true,
      isLoading: false,
      results: [
        makeCharacterVoiceResult({ character_name: "Elena" }),
        makeCharacterVoiceResult({ character_name: "Marcus" }),
      ],
    });

    render(<CharacterVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Elena")).toBeInTheDocument();
    });

    expect(screen.getByText("Marcus")).toBeInTheDocument();
  });

  it("renders the persisted voice-profile metric field labels", async () => {
    setState({
      isComplete: true,
      isLoading: false,
      results: [makeCharacterVoiceResult()],
    });

    render(<CharacterVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("characterVoice.formality")).toBeInTheDocument();
    });

    expect(screen.getByText("characterVoice.vocabularyLevel")).toBeInTheDocument();
    expect(screen.getByText("characterVoice.sentenceProfile")).toBeInTheDocument();
    expect(screen.getByText("characterVoice.emotionalRange")).toBeInTheDocument();
    expect(screen.getByText("characterVoice.culturalRegionalMarkers")).toBeInTheDocument();
    expect(screen.getByText("characterVoice.voiceExamples")).toBeInTheDocument();
  });

  it("renders formality as a percentage of the persisted value", async () => {
    setState({
      isComplete: true,
      isLoading: false,
      results: [makeCharacterVoiceResult()],
    });

    render(<CharacterVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("72%")).toBeInTheDocument();
    });
  });

  it("renders the categorical profile values", async () => {
    setState({
      isComplete: true,
      isLoading: false,
      results: [makeCharacterVoiceResult()],
    });

    render(<CharacterVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("moderate")).toBeInTheDocument();
    });

    expect(screen.getByText("varied")).toBeInTheDocument();
    expect(screen.getByText("expressive")).toBeInTheDocument();
  });

  it("renders curated voice example quotes", async () => {
    setState({
      isComplete: true,
      isLoading: false,
      results: [makeCharacterVoiceResult()],
    });

    render(<CharacterVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("characterVoice.voiceExamples")).toBeInTheDocument();
    });

    expect(screen.getByText(/\u201cBy the stars/)).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Results — distinctiveness_notes display-only labelling (ADR-055 Decision 1)
  // -------------------------------------------------------------------------

  it("renders distinctiveness notes with a display-only caveat", async () => {
    setState({
      isComplete: true,
      isLoading: false,
      results: [makeCharacterVoiceResult()],
    });

    render(<CharacterVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("characterVoice.distinctivenessNotes")).toBeInTheDocument();
    });

    // The per-run comparison copy is surfaced verbatim...
    expect(screen.getByText(/Elena.*nautical idioms.*Marcus.*terse brevity/)).toBeInTheDocument();
    // ...and clearly labelled as a per-run comparison, not stored.
    expect(screen.getByText("characterVoice.distinctivenessCaveat")).toBeInTheDocument();
  });

  it("does not render distinctiveness section when notes are absent", async () => {
    setState({
      isComplete: true,
      isLoading: false,
      results: [makeCharacterVoiceResult({ distinctiveness_notes: null })],
    });

    render(<CharacterVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Elena")).toBeInTheDocument();
    });

    expect(screen.queryByText("characterVoice.distinctivenessNotes")).not.toBeInTheDocument();
    expect(screen.queryByText("characterVoice.distinctivenessCaveat")).not.toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Results — empty / missing profile
  // -------------------------------------------------------------------------

  it("shows no-results message when the result array is empty", async () => {
    setState({ isComplete: true, isLoading: false, results: [] });

    render(<CharacterVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("characterVoice.noResults")).toBeInTheDocument();
    });
  });

  it("shows a no-profile message when voice_analysis is null but keeps the name", async () => {
    setState({
      isComplete: true,
      isLoading: false,
      results: [makeCharacterVoiceResult({ voice_analysis: null })],
    });

    render(<CharacterVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Elena")).toBeInTheDocument();
    });

    expect(screen.getByText("characterVoice.noVoiceProfile")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Error state
  // -------------------------------------------------------------------------

  it("renders error state with retry button when analysis fails", async () => {
    setState({ isError: true, isLoading: false, error: networkError("Network error") });

    render(<CharacterVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("characterVoice.analysisFailed")).toBeInTheDocument();
    });

    expect(screen.getByText("Network error")).toBeInTheDocument();
    expect(screen.getByText("retry")).toBeInTheDocument();
  });

  it("retry button triggers re-analysis", async () => {
    const user = userEvent.setup();
    setState({ isError: true, isLoading: false, error: networkError("fail") });

    render(<CharacterVoicePanel {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("retry")).toBeInTheDocument();
    });

    await user.click(screen.getByText("retry"));

    // Once on mount, once on retry.
    expect(mockRun).toHaveBeenCalledTimes(2);
  });

  // -------------------------------------------------------------------------
  // Refresh
  // -------------------------------------------------------------------------

  it("refresh button triggers re-analysis in results state", async () => {
    const user = userEvent.setup();
    setState({
      isComplete: true,
      isLoading: false,
      results: [makeCharacterVoiceResult()],
    });

    render(<CharacterVoicePanel {...defaultProps} />);

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
    render(<CharacterVoicePanel {...defaultProps} chapterIds={[]} />);

    expect(mockRun).not.toHaveBeenCalled();
    expect(screen.queryByText("characterVoice.analyzing")).not.toBeInTheDocument();
  });
});
