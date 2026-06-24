/**
 * Intensity derivation tests — CR-AUFG-07-23
 *
 * Pure-function tests for deriving Emotional Intensity Curve points from
 * existing ANAL-002 SentimentOverview data.
 */
import { describe, expect, it } from "vitest";
import type { SentimentOverview } from "@/lib/api/analysis";
import {
  arousalToIntensity,
  deriveIntensityPoints,
  type IntensityChapter,
  type IntensityPoint,
  type IntensityWarning,
  MIN_SENTENCES_FOR_RELIABLE,
} from "./intensity";

// --- Fixtures ----------------------------------------------------------------

function makeOverview(overrides: Partial<SentimentOverview> = {}): SentimentOverview {
  return {
    sentence_count: 12,
    average_vad: { valence: 0.5, arousal: 0.3, dominance: 0.7 },
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

// --- arousalToIntensity ------------------------------------------------------

describe("arousalToIntensity", () => {
  it("maps arousal -1 (calm) to intensity 0", () => {
    expect(arousalToIntensity(-1)).toBe(0);
  });

  it("maps arousal +1 (excited) to intensity 100", () => {
    expect(arousalToIntensity(1)).toBe(100);
  });

  it("maps arousal 0 (neutral) to intensity 50", () => {
    expect(arousalToIntensity(0)).toBe(50);
  });

  it("clamps arousal above +1 to 100", () => {
    expect(arousalToIntensity(1.5)).toBe(100);
  });

  it("clamps arousal below -1 to 0", () => {
    expect(arousalToIntensity(-1.5)).toBe(0);
  });

  it("maps a mid-range arousal value proportionally", () => {
    // 0.4 -> (0.4 + 1) / 2 * 100 = 70
    expect(arousalToIntensity(0.4)).toBe(70);
  });
});

// --- deriveIntensityPoints ---------------------------------------------------

describe("deriveIntensityPoints", () => {
  it("returns one point per result, preserving order", () => {
    const results = [
      makeOverview({ average_vad: { valence: 0, arousal: -0.5, dominance: 0 } }),
      makeOverview({ average_vad: { valence: 0, arousal: 0.5, dominance: 0 } }),
    ];

    const points = deriveIntensityPoints(results);

    expect(points).toHaveLength(2);
    expect(points[0].order).toBe(0);
    expect(points[1].order).toBe(1);
  });

  it("derives arousal and normalized intensity from average_vad", () => {
    const results = [makeOverview({ average_vad: { valence: 0, arousal: 0.6, dominance: 0 } })];

    const [point] = deriveIntensityPoints(results);

    expect(point?.arousal).toBe(0.6);
    // (0.6 + 1) / 2 * 100 = 80
    expect(point?.intensity).toBe(80);
  });

  it("carries chapter id and title from the optional chapters prop", () => {
    const results = [makeOverview()];
    const chapters: IntensityChapter[] = [{ id: "ch-1", title: "The Beginning" }];

    const [point] = deriveIntensityPoints(results, chapters);

    expect(point?.chapterId).toBe("ch-1");
    expect(point?.chapterTitle).toBe("The Beginning");
  });

  it("falls back to null id and empty title when chapters prop is omitted", () => {
    const [point] = deriveIntensityPoints([makeOverview()]);

    expect(point?.chapterId).toBeNull();
    expect(point?.chapterTitle).toBe("");
  });

  it("adds an insufficient-sentences warning when sentence_count is below threshold", () => {
    const results = [makeOverview({ sentence_count: MIN_SENTENCES_FOR_RELIABLE - 1 })];

    const [point] = deriveIntensityPoints(results);

    const warning: IntensityWarning | undefined = point?.warnings.find(
      (w) => w.kind === "insufficient_sentences",
    );
    expect(warning).toBeDefined();
  });

  it("adds no warnings when sentence_count meets the threshold", () => {
    const results = [makeOverview({ sentence_count: MIN_SENTENCES_FOR_RELIABLE })];

    const [point] = deriveIntensityPoints(results);

    expect(point?.warnings).toHaveLength(0);
  });

  it("takes confidence from narrative_arc when present", () => {
    const results = [
      makeOverview({
        narrative_arc: {
          arc_type: "Fall",
          confidence: 0.42,
          segments: [],
          explanation: "Declining.",
        },
      }),
    ];

    const [point] = deriveIntensityPoints(results);

    expect(point?.confidence).toBe(0.42);
  });

  it("returns null confidence when narrative_arc is absent", () => {
    const results = [makeOverview({ narrative_arc: null })];

    const [point] = deriveIntensityPoints(results);

    expect(point?.confidence).toBeNull();
  });

  it("returns an empty array for no results", () => {
    expect(deriveIntensityPoints([])).toEqual<IntensityPoint[]>([]);
  });

  it("produces stable intensity ordering for a rising story", () => {
    const results = [
      makeOverview({ average_vad: { valence: 0, arousal: -0.8, dominance: 0 } }),
      makeOverview({ average_vad: { valence: 0, arousal: 0, dominance: 0 } }),
      makeOverview({ average_vad: { valence: 0, arousal: 0.9, dominance: 0 } }),
    ];

    const points = deriveIntensityPoints(results);
    const intensities = points.map((p) => p.intensity);

    expect(intensities).toEqual([10, 50, 95]);
    // Strictly increasing — the curve reflects a rising arc.
    expect(intensities[1]).toBeGreaterThan(intensities[0]!);
    expect(intensities[2]).toBeGreaterThan(intensities[1]!);
  });
});
