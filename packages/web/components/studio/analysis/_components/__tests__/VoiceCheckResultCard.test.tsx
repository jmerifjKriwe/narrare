/**
 * VoiceCheckResultCard tests — WRITE-010.
 *
 * Direct unit tests for ONE character's voice-check result card (the card has
 * real conditional logic — band color mapping, null-score / no-profile graceful
 * states, flagged lines — that is best covered at the card level). The card
 * takes the same `t` translator prop as CharacterVoiceResultCard; a local mock
 * mirrors next-intl's key-returning behaviour (param interpolation into the
 * returned key string).
 *
 * @module VoiceCheckResultCard.test
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VoiceCheckResultCard } from "@/components/studio/analysis/_components/VoiceCheckResultCard";
import type { VoiceCheckResult } from "@/lib/api/voice-check-stream";

/** Mirrors the global next-intl mock: returns the key, interpolating params. */
function makeT() {
  return (key: string, values?: Record<string, string | number | Date>): string => {
    if (!values) return key;
    return Object.entries(values).reduce((str, [k, v]) => str.replace(`{${k}}`, String(v)), key);
  };
}

const t = makeT();

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

describe("VoiceCheckResultCard", () => {
  // -------------------------------------------------------------------------
  // Fully-scored character
  // -------------------------------------------------------------------------

  it("renders the character name", () => {
    render(<VoiceCheckResultCard result={makeResult()} t={t} />);

    expect(screen.getByText("Elena")).toBeInTheDocument();
  });

  it("renders the match score label + a progressbar carrying the score value", () => {
    render(<VoiceCheckResultCard result={makeResult({ match_score: 88 })} t={t} />);

    expect(screen.getByText("voiceCheck.matchScore")).toBeInTheDocument();
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "88");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
  });

  it("renders the band label for the result's band", () => {
    render(<VoiceCheckResultCard result={makeResult({ band: "fair" })} t={t} />);

    expect(screen.getByText("voiceCheck.band.fair")).toBeInTheDocument();
  });

  it("renders the judgment label when present", () => {
    render(<VoiceCheckResultCard result={makeResult({ match_judgment: "notable_drift" })} t={t} />);

    expect(screen.getByText("voiceCheck.judgment.notable_drift")).toBeInTheDocument();
  });

  it("renders the qualitative + metric sub-scores as percentages", () => {
    render(
      <VoiceCheckResultCard
        result={makeResult({ qualitative_sub_score: 77, metric_delta_subscore: 81 })}
        t={t}
      />,
    );

    expect(screen.getByText("voiceCheck.qualitativeSubScore")).toBeInTheDocument();
    expect(screen.getByText("voiceCheck.metricDeltaSubScore")).toBeInTheDocument();
    expect(screen.getByText("77%")).toBeInTheDocument();
    expect(screen.getByText("81%")).toBeInTheDocument();
  });

  it("renders the comparable-metrics line", () => {
    render(<VoiceCheckResultCard result={makeResult({ n_comparable_metrics: 6 })} t={t} />);

    expect(screen.getByText("voiceCheck.nComparableMetrics")).toBeInTheDocument();
  });

  it("renders flagged lines with the quote, reason, and reason label", () => {
    render(<VoiceCheckResultCard result={makeResult()} t={t} />);

    expect(screen.getByText("voiceCheck.flaggedLines")).toBeInTheDocument();
    expect(screen.getByText(/\u201cYou won/)).toBeInTheDocument();
    expect(screen.getByText("voiceCheck.flaggedLineReason")).toBeInTheDocument();
    expect(screen.getByText("Slightly more formal than profile.")).toBeInTheDocument();
  });

  it("does not render a flagged-lines section when there are none", () => {
    render(<VoiceCheckResultCard result={makeResult({ flagged_lines: [] })} t={t} />);

    expect(screen.queryByText("voiceCheck.flaggedLines")).not.toBeInTheDocument();
  });

  it("rounds the match score to a whole number in the progressbar", () => {
    render(<VoiceCheckResultCard result={makeResult({ match_score: 92.4 })} t={t} />);

    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "92");
  });

  // -------------------------------------------------------------------------
  // Graceful states
  // -------------------------------------------------------------------------

  it("shows noVoiceProfile and no score block when the character has no profile", () => {
    render(
      <VoiceCheckResultCard
        result={makeResult({
          has_profile: false,
          match_score: null,
          band: null,
          match_judgment: null,
          qualitative_sub_score: null,
          metric_delta_subscore: null,
          flagged_lines: [],
          n_comparable_metrics: 0,
        })}
        t={t}
      />,
    );

    expect(screen.getByText("voiceCheck.noVoiceProfile")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.queryByText("voiceCheck.band.green")).not.toBeInTheDocument();
  });

  it("shows noScore (but keeps the name) when profiled but unscorable", () => {
    render(
      <VoiceCheckResultCard
        result={makeResult({ match_score: null, band: null, match_judgment: null })}
        t={t}
      />,
    );

    expect(screen.getByText("voiceCheck.noScore")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect(screen.getByText("Elena")).toBeInTheDocument();
  });
});
