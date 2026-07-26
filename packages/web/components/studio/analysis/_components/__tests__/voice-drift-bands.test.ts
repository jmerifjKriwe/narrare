/**
 * voice-drift-bands unit tests — band metadata + badge composition (ANAL-009).
 *
 * Pure presentational logic: verifies the band → symbol / colour mapping is
 * complete and the ADR-073 Decision 4 badge-composition rule (band +
 * drift_type → classification label) matches the approved mockup.
 *
 * @module voice-drift-bands.test
 */

import { describe, expect, it } from "vitest";
import {
  composeClassification,
  DRIFT_BAND_ORDER,
  DRIFT_BANDS,
  formatMatchPercent,
} from "@/components/studio/analysis/_components/voice-drift-bands";
import type { VoiceDriftBand, VoiceDriftType } from "@/lib/api/voice-drift-stream";

describe("DRIFT_BANDS metadata", () => {
  it("covers all four bands with a symbol + tailwind tokens", () => {
    const bands: VoiceDriftBand[] = ["stable", "minor", "moderate", "major"];
    for (const band of bands) {
      const meta = DRIFT_BANDS[band];
      expect(meta.symbol.length).toBeGreaterThan(0);
      expect(meta.text).toContain("text-");
      expect(meta.cellBg).toContain("bg-");
      expect(meta.cellBorder).toContain("border-");
      expect(meta.badge.length).toBeGreaterThan(0);
    }
  });

  it("DRIFT_BAND_ORDER is stable → minor → moderate → major", () => {
    expect(DRIFT_BAND_ORDER).toEqual(["stable", "minor", "moderate", "major"]);
  });
});

describe("composeClassification (ADR-073 Decision 4)", () => {
  it("stable band → 'stable' regardless of drift_type", () => {
    const types: VoiceDriftType[] = ["evolution", "context", "inconsistency"];
    for (const driftType of types) {
      expect(composeClassification("stable", driftType)).toBe("stable");
    }
  });

  it("minor band → 'mildVariation' regardless of drift_type", () => {
    const types: VoiceDriftType[] = ["evolution", "context", "inconsistency"];
    for (const driftType of types) {
      expect(composeClassification("minor", driftType)).toBe("mildVariation");
    }
  });

  it("moderate/major band surfaces the agent's drift_type label", () => {
    expect(composeClassification("moderate", "evolution")).toBe("evolution");
    expect(composeClassification("moderate", "context")).toBe("context");
    expect(composeClassification("moderate", "inconsistency")).toBe("inconsistency");
    expect(composeClassification("major", "inconsistency")).toBe("inconsistency");
    expect(composeClassification("major", "evolution")).toBe("evolution");
  });

  it("null band (unscorable) → no badge", () => {
    expect(composeClassification(null, "evolution")).toBeNull();
    expect(composeClassification(null, "inconsistency")).toBeNull();
  });
});

describe("formatMatchPercent", () => {
  it("rounds the score to a whole-number percent", () => {
    expect(formatMatchPercent(87.4)).toBe("87%");
    expect(formatMatchPercent(62.6)).toBe("63%");
    expect(formatMatchPercent(100)).toBe("100%");
    expect(formatMatchPercent(0)).toBe("0%");
  });

  it("returns null when the score is null (unscorable)", () => {
    expect(formatMatchPercent(null)).toBeNull();
  });
});
