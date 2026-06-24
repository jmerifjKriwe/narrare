/**
 * EmotionalIntensityCurve tests — CR-AUFG-07-23
 *
 * Tests: empty state, insufficient data, chart rendering, point click,
 * data-quality warnings, export button, and accessibility (ARIA labels +
 * table alternative).
 *
 * next-intl is globally mocked in setupTests.ts (returns keys directly).
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { SentimentOverview } from "@/lib/api/analysis";
import { EmotionalIntensityCurve } from "./EmotionalIntensityCurve";

// --- Fixtures ----------------------------------------------------------------

function makeOverview(overrides: Partial<SentimentOverview> = {}): SentimentOverview {
  return {
    sentence_count: 10,
    average_vad: { valence: 0.4, arousal: 0.5, dominance: 0.6 },
    overall_emotions: {
      anger: 0.1,
      anticipation: 0.2,
      disgust: 0,
      fear: 0.1,
      joy: 0.5,
      sadness: 0.1,
      surprise: 0,
      trust: 0.4,
      positive: 0.6,
      negative: 0.1,
    },
    narrative_arc: {
      arc_type: "Rise",
      confidence: 0.8,
      segments: [],
      explanation: "A rising trajectory.",
    },
    sentences: [],
    dominant_emotions: ["joy"],
    ...overrides,
  };
}

// --- Tests -------------------------------------------------------------------

describe("EmotionalIntensityCurve", () => {
  it("renders the empty state when there are no results", () => {
    render(<EmotionalIntensityCurve results={[]} />);

    expect(screen.getByText("emotionalIntensity.empty")).toBeInTheDocument();
  });

  it("renders the insufficient-data state when only one result is present", () => {
    render(<EmotionalIntensityCurve results={[makeOverview()]} />);

    expect(screen.getByText("emotionalIntensity.insufficientData")).toBeInTheDocument();
  });

  it("renders the chart section when two or more results are present", () => {
    render(
      <EmotionalIntensityCurve
        results={[
          makeOverview({ average_vad: { valence: 0, arousal: -0.5, dominance: 0 } }),
          makeOverview(),
        ]}
      />,
    );

    // Section is labelled via aria-label
    expect(screen.getByRole("img", { name: "emotionalIntensity.title" })).toBeInTheDocument();
  });

  it("renders one table row per chapter in the data alternative", () => {
    render(
      <EmotionalIntensityCurve
        results={[
          makeOverview({ average_vad: { valence: 0, arousal: -0.2, dominance: 0 } }),
          makeOverview({ average_vad: { valence: 0, arousal: 0.6, dominance: 0 } }),
          makeOverview({ average_vad: { valence: 0, arousal: 0.1, dominance: 0 } }),
        ]}
      />,
    );

    const table = screen.getByRole("table");
    // 3 chapter rows (header row is not a tbody row)
    expect(within(table).getAllByRole("row")).toHaveLength(4); // 1 header + 3 data
  });

  it("calls onPointClick with the chapter index when a data row is clicked", async () => {
    const user = userEvent.setup();
    const onPointClick = vi.fn();

    render(
      <EmotionalIntensityCurve
        results={[
          makeOverview({ average_vad: { valence: 0, arousal: -0.3, dominance: 0 } }),
          makeOverview({ average_vad: { valence: 0, arousal: 0.7, dominance: 0 } }),
        ]}
        onPointClick={onPointClick}
      />,
    );

    // Each chapter cell is a keyboard-accessible button (keeps table row semantics).
    const table = screen.getByRole("table");
    const buttons = within(table).getAllByRole("button");
    await user.click(buttons[1]!);

    expect(onPointClick).toHaveBeenCalledWith(1);
  });

  it("shows an insufficient-sentences warning when sentence_count is low", () => {
    render(
      <EmotionalIntensityCurve
        results={[makeOverview({ sentence_count: 1 }), makeOverview({ sentence_count: 20 })]}
      />,
    );

    // Warning key appears in the table for the low-sentence chapter
    expect(
      screen.getByText("emotionalIntensity.warnings.insufficientSentences"),
    ).toBeInTheDocument();
  });

  it("renders the export button", () => {
    render(<EmotionalIntensityCurve results={[makeOverview(), makeOverview()]} />);

    expect(screen.getByLabelText("emotionalIntensity.exportChart")).toBeInTheDocument();
  });

  it("provides an accessible aria-label on the chart", () => {
    render(<EmotionalIntensityCurve results={[makeOverview(), makeOverview()]} />);

    const chart = screen.getByRole("img", { name: "emotionalIntensity.title" });
    expect(chart).toBeInTheDocument();
  });

  it("labels each data point for screen readers", () => {
    render(
      <EmotionalIntensityCurve
        results={[
          makeOverview({ average_vad: { valence: 0, arousal: 0.4, dominance: 0 } }),
          makeOverview(),
        ]}
        chapters={[
          { id: "ch-1", title: "The Beginning" },
          { id: "ch-2", title: "The End" },
        ]}
      />,
    );

    // pointAriaLabel resolves to "Chapter {chapter}: estimated intensity {intensity}"
    // One button per chapter carries the aria-label.
    const labelled = screen.getAllByLabelText("emotionalIntensity.pointAriaLabel");
    expect(labelled).toHaveLength(2);
  });

  it("uses positional chapter labels when no chapter titles are provided", () => {
    render(<EmotionalIntensityCurve results={[makeOverview(), makeOverview()]} />);

    // Table rows contain positional chapter labels (Chapter 1, Chapter 2)
    const table = screen.getByRole("table");
    expect(within(table).getAllByText("emotionalIntensity.chapterLabel")).toHaveLength(2);
  });
});
