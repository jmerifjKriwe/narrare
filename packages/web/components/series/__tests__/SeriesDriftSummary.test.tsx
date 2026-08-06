/**
 * SeriesDriftSummary component tests (Spec 4 Task 4).
 *
 * Pure presentational component. Verifies the three branches of the reused
 * AuthorVoiceDriftResponse shape: the RULE-11 graceful no-profile skip, the
 * positive no-drift state (stable / unscorable band), and the drift-warnings
 * state (minor/moderate/major band with reasons + attention chapters).
 *
 * Conventions: setupTests.ts returns i18n KEY STRINGS verbatim.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SeriesDriftSummary } from "@/components/series/SeriesDriftSummary";
import type { SeriesVoiceDriftResult } from "@/types";

function makeResponse(overrides: Partial<SeriesVoiceDriftResult> = {}): SeriesVoiceDriftResult {
  return { novel_id: "novel-2", result: null, no_profile: null, ...overrides };
}

describe("SeriesDriftSummary", () => {
  it("renders the graceful no-profile skip when no_profile is set", () => {
    const response = makeResponse({
      no_profile: { reason: "no_stored_profile" },
    });
    render(<SeriesDriftSummary response={response} />);
    expect(screen.getByTestId("series-drift-no-profile").textContent).toContain(
      "series.drift.noProfileReason.no_stored_profile",
    );
  });

  it("renders the positive no-drift state when the band is stable", () => {
    const response = makeResponse({
      result: {
        novel_id: "novel-2",
        trend: [],
        jumps: [],
        overall_match_score: 95,
        overall_band: "stable",
        drift: {
          drift_type: "evolution",
          confidence: 0.9,
          longitudinal_reasons: [],
          per_chapter_notes: [],
          suggested_attention: [],
        },
      },
    });
    render(<SeriesDriftSummary response={response} />);
    expect(screen.getByTestId("series-drift-empty").textContent).toContain("series.drift.noDrift");
    expect(screen.queryByTestId("series-drift-warnings")).toBeNull();
  });

  it("renders the positive no-drift state when the band is unscorable (null)", () => {
    const response = makeResponse({
      result: {
        novel_id: "novel-2",
        trend: [],
        jumps: [],
        overall_match_score: null,
        overall_band: null,
        drift: {
          drift_type: "evolution",
          confidence: 0.5,
          longitudinal_reasons: [],
          per_chapter_notes: [],
          suggested_attention: [],
        },
      },
    });
    render(<SeriesDriftSummary response={response} />);
    expect(screen.getByTestId("series-drift-empty")).toBeDefined();
  });

  it("renders drift warnings (band badge, classification, reasons, attention) for a moderate band", () => {
    const response = makeResponse({
      result: {
        novel_id: "novel-2",
        trend: [],
        jumps: [],
        overall_match_score: 60,
        overall_band: "moderate",
        drift: {
          drift_type: "inconsistency",
          confidence: 0.8,
          longitudinal_reasons: ["Dialogue grew terser from chapter 3."],
          per_chapter_notes: [],
          suggested_attention: ["chapter-3", "chapter-7"],
        },
      },
    });
    render(<SeriesDriftSummary response={response} />);

    expect(screen.getByTestId("series-drift-warnings")).toBeDefined();
    expect(screen.getByTestId("series-drift-band-moderate").textContent).toContain(
      "series.drift.band.moderate",
    );
    expect(screen.getByTestId("series-drift-reasons").textContent).toContain(
      "Dialogue grew terser from chapter 3.",
    );
    expect(screen.getByTestId("series-drift-attention").textContent).toContain("chapter-3");
    expect(screen.getByTestId("series-drift-attention").textContent).toContain("chapter-7");
  });

  it("renders warnings without the reasons/attention blocks when those are empty", () => {
    const response = makeResponse({
      result: {
        novel_id: "novel-2",
        trend: [],
        jumps: [],
        overall_match_score: 40,
        overall_band: "major",
        drift: {
          drift_type: "context",
          confidence: 0.7,
          longitudinal_reasons: [],
          per_chapter_notes: [],
          suggested_attention: [],
        },
      },
    });
    render(<SeriesDriftSummary response={response} />);

    expect(screen.getByTestId("series-drift-band-major")).toBeDefined();
    expect(screen.queryByTestId("series-drift-reasons")).toBeNull();
    expect(screen.queryByTestId("series-drift-attention")).toBeNull();
  });
});
