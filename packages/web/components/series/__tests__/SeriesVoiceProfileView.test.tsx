/**
 * SeriesVoiceProfileView component tests (Spec 3, Tasks 5–6).
 *
 * Pure presentational component — renders the descriptive group of a stored
 * series-voice profile (ADR-074 binding: metrics are never rendered). No hooks,
 * so no mocking beyond the global i18n stub.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SeriesVoiceProfileView } from "@/components/series/SeriesVoiceProfileView";
import type { SeriesVoiceProfile } from "@/types";

const profile: SeriesVoiceProfile = {
  voice_analysis: {
    vocabulary_level: "literary",
    sentence_profile: "long, flowing",
    emotional_range: "melancholic",
    cultural_regional_markers: "Scottish Highlands",
    voice_examples: ["The rain fell like memory."],
    // Comparison-only — must NEVER render (ADR-074 binding).
    voice_metrics: { avg_sentence_length: 24.5 },
  },
  author_examples: ["The moor was silent."],
  author_metrics: { lexical_diversity: 0.71 },
  updated_at: "2026-08-04T10:00:00Z",
  is_fresh: true,
};

describe("SeriesVoiceProfileView", () => {
  it("renders the descriptive voice-analysis fields", () => {
    render(<SeriesVoiceProfileView profile={profile} />);
    const view = screen.getByTestId("series-voice-profile");
    const text = view.textContent ?? "";
    expect(text).toContain("literary");
    expect(text).toContain("long, flowing");
    expect(text).toContain("melancholic");
    expect(text).toContain("Scottish Highlands");
  });

  it("renders the curated author examples", () => {
    render(<SeriesVoiceProfileView profile={profile} />);
    expect(screen.getByTestId("series-voice-profile").textContent).toContain(
      "The moor was silent.",
    );
  });

  it("renders the updated-at timestamp", () => {
    render(<SeriesVoiceProfileView profile={profile} />);
    expect(screen.getByTestId("series-voice-profile-updated-at")).toBeDefined();
  });

  it("renders an empty state when the profile has no descriptive data", () => {
    render(<SeriesVoiceProfileView profile={{ voice_analysis: null, author_examples: null }} />);
    expect(screen.getByTestId("series-voice-profile-empty")).toBeDefined();
  });
});
