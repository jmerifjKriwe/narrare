/**
 * BetaReaderPanelContent tests — tab content renderer for beta reader.
 *
 * Tests:
 * 1. Renders loading state
 * 2. Renders error state with retry
 * 3. Returns null for idle state
 * 4. Renders strengths tab
 * 5. Renders issues tab
 * 6. Renders questions tab
 * 7. Renders overall tab with ScoreRadar
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BetaReaderPanelContent } from "@/components/studio/analysis/BetaReaderPanelContent";
import type { BetaReaderResponse } from "@/lib/api/analysis";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/components/studio/analysis/FeedbackCard", () => ({
  FeedbackCard: ({ item }: { item: { title: string } }) => (
    <div data-testid="feedback-card">{item.title}</div>
  ),
  strengthCardItem: (s: { title: string }) => s,
  feedbackCardItem: (f: { title: string }) => f,
  questionCardItem: (q: { question: string }) => ({ title: q.question }),
}));

vi.mock("@/components/studio/analysis/ScoreRadar", () => ({
  ScoreRadar: ({ scores }: { scores: { key: string; value: number; label: string }[] }) => (
    <div data-testid="score-radar">{scores.map((s) => `${s.label}: ${s.value}`).join(", ")}</div>
  ),
  createScoreDimensions: (
    overall: {
      reader_engagement: number;
      emotional_impact: number;
      pacing_score: number;
      prose_quality: number;
      plot_progression: number;
      character_development: number;
    },
    t: (key: string) => string,
  ) => [
    { key: "engagement", value: overall.reader_engagement, label: t("overall.engagement") },
    { key: "emotional", value: overall.emotional_impact, label: t("overall.emotionalImpact") },
    { key: "pacing", value: overall.pacing_score, label: t("overall.pacing") },
    { key: "prose", value: overall.prose_quality, label: t("overall.proseQuality") },
    { key: "plot", value: overall.plot_progression, label: t("overall.plotProgression") },
    { key: "char", value: overall.character_development, label: t("overall.characterDev") },
  ],
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const t = (key: string) => key;

function createResult(): BetaReaderResponse {
  return {
    novel_id: "novel-1",
    chapter_ids: ["ch-1"],
    total_word_count: 5200,
    strengths: [
      {
        category: "prose",
        title: "Good dialogue",
        description: "Natural-sounding dialogue",
        text_excerpt: "p.3",
      },
    ],
    feedback: [
      {
        category: "pacing",
        title: "Slow start",
        description: "Opening drags",
        severity: "moderate",
        location: "Ch.1",
        suggestion: null,
        text_excerpt: null,
      },
    ],
    questions: [
      { category: "plot", question: "Why does Anna leave?", context: "Chapter 3", location: null },
    ],
    overall: {
      reader_engagement: 7,
      emotional_impact: 8,
      pacing_score: 6,
      prose_quality: 7,
      plot_progression: 5,
      character_development: 8,
      summary: "Strong character work, pacing needs attention.",
    },
    analyzed_at: "2026-05-27T10:00:00Z",
    cache_key: "cache-abc123",
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BetaReaderPanelContent", () => {
  it("renders loading state", () => {
    render(
      <BetaReaderPanelContent
        viewState="loading"
        activeTab="strengths"
        result={null}
        error={null}
        isPending={false}
        onRetry={vi.fn()}
        t={t}
      />,
    );

    expect(screen.getByText("loading")).toBeDefined();
    expect(screen.getByText("loadingSubtext")).toBeDefined();
  });

  it("renders error state with retry button", () => {
    render(
      <BetaReaderPanelContent
        viewState="error"
        activeTab="strengths"
        result={null}
        error={new Error("Analysis failed")}
        isPending={false}
        onRetry={vi.fn()}
        t={t}
      />,
    );

    expect(screen.getByText("error")).toBeDefined();
    expect(screen.getByText("retry")).toBeDefined();
  });

  it("calls onRetry when retry button clicked", () => {
    const onRetry = vi.fn();
    render(
      <BetaReaderPanelContent
        viewState="error"
        activeTab="strengths"
        result={null}
        error={new Error("Failed")}
        isPending={false}
        onRetry={onRetry}
        t={t}
      />,
    );

    fireEvent.click(screen.getByText("retry"));
    expect(onRetry).toHaveBeenCalled();
  });

  it("returns null for idle state", () => {
    const { container } = render(
      <BetaReaderPanelContent
        viewState="idle"
        activeTab="strengths"
        result={null}
        error={null}
        isPending={false}
        onRetry={vi.fn()}
        t={t}
      />,
    );

    expect(container.innerHTML).toBe("");
  });

  it("renders strengths tab content", () => {
    render(
      <BetaReaderPanelContent
        viewState="results"
        activeTab="strengths"
        result={createResult()}
        error={null}
        isPending={false}
        onRetry={vi.fn()}
        t={t}
      />,
    );

    expect(screen.getByTestId("feedback-card")).toBeDefined();
  });

  it("renders issues tab content", () => {
    render(
      <BetaReaderPanelContent
        viewState="results"
        activeTab="issues"
        result={createResult()}
        error={null}
        isPending={false}
        onRetry={vi.fn()}
        t={t}
      />,
    );

    expect(screen.getByTestId("feedback-card")).toBeDefined();
  });

  it("renders questions tab content", () => {
    render(
      <BetaReaderPanelContent
        viewState="results"
        activeTab="questions"
        result={createResult()}
        error={null}
        isPending={false}
        onRetry={vi.fn()}
        t={t}
      />,
    );

    expect(screen.getByTestId("feedback-card")).toBeDefined();
  });

  it("renders overall tab with ScoreRadar", () => {
    render(
      <BetaReaderPanelContent
        viewState="results"
        activeTab="overall"
        result={createResult()}
        error={null}
        isPending={false}
        onRetry={vi.fn()}
        t={t}
      />,
    );

    expect(screen.getByTestId("score-radar")).toBeDefined();
  });

  it("renders summary in overall tab", () => {
    render(
      <BetaReaderPanelContent
        viewState="results"
        activeTab="overall"
        result={createResult()}
        error={null}
        isPending={false}
        onRetry={vi.fn()}
        t={t}
      />,
    );

    expect(screen.getByText("Strong character work, pacing needs attention.")).toBeDefined();
  });
});
