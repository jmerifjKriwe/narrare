/**
 * ScoreRadar tests — radar chart for beta reader scores.
 *
 * Tests:
 * 1. Renders radar chart container
 * 2. Renders with correct aria-label
 * 3. createScoreDimensions returns 6 dimensions
 * 4. createScoreDimensions maps scores correctly
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createScoreDimensions, ScoreRadar } from "@/components/studio/analysis/ScoreRadar";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("recharts", () => ({
  RadarChart: ({ data }: { data: { dimension: string; value: number }[] }) => (
    <div data-testid="radar-chart">
      {data.map((d) => (
        <span key={d.dimension}>
          {d.dimension}: {d.value}
        </span>
      ))}
    </div>
  ),
  Radar: () => <div data-testid="radar-area" />,
  PolarGrid: () => null,
  PolarAngleAxis: () => null,
  PolarRadiusAxis: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const t = (key: string) => key;

const defaultScores = [
  { key: "engagement", value: 7, label: "overall.engagement" },
  { key: "emotional", value: 8, label: "overall.emotionalImpact" },
  { key: "pacing", value: 6, label: "overall.pacing" },
  { key: "prose", value: 7, label: "overall.proseQuality" },
  { key: "plot", value: 5, label: "overall.plotProgression" },
  { key: "char", value: 8, label: "overall.characterDev" },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ScoreRadar", () => {
  it("renders radar chart container", () => {
    render(<ScoreRadar scores={defaultScores} />);

    expect(screen.getByTestId("radar-chart")).toBeDefined();
  });

  it("renders with correct aria-label", () => {
    render(<ScoreRadar scores={defaultScores} />);

    const container = screen.getByRole("img");
    expect(container).toBeDefined();
    expect(container.getAttribute("aria-label")).toBe("overall.scores");
  });

  it("renders all score labels", () => {
    render(<ScoreRadar scores={defaultScores} />);

    expect(screen.getByText(/overall.engagement: 7/)).toBeDefined();
    expect(screen.getByText(/overall.emotionalImpact: 8/)).toBeDefined();
    expect(screen.getByText(/overall.pacing: 6/)).toBeDefined();
  });

  it("uses custom fill color when provided", () => {
    render(<ScoreRadar scores={defaultScores} fillColor="red" strokeColor="darkred" />);

    // Component renders without error with custom colors
    expect(screen.getByTestId("radar-chart")).toBeDefined();
  });
});

describe("createScoreDimensions", () => {
  it("returns 6 dimensions", () => {
    const dimensions = createScoreDimensions(
      {
        reader_engagement: 7,
        emotional_impact: 8,
        pacing_score: 6,
        prose_quality: 7,
        plot_progression: 5,
        character_development: 8,
      },
      t,
    );

    expect(dimensions).toHaveLength(6);
  });

  it("maps scores correctly with labels", () => {
    const dimensions = createScoreDimensions(
      {
        reader_engagement: 7,
        emotional_impact: 8,
        pacing_score: 6,
        prose_quality: 7,
        plot_progression: 5,
        character_development: 8,
      },
      t,
    );

    expect(dimensions[0]).toEqual({
      key: "reader_engagement",
      value: 7,
      label: "overall.engagement",
    });
    expect(dimensions[5]).toEqual({
      key: "character_development",
      value: 8,
      label: "overall.characterDev",
    });
  });
});
