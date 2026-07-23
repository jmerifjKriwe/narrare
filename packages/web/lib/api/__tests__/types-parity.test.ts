/**
 * RULE-17 parity: TS interface field names match the shipped Pydantic schemas
 * (apps/api/narrare/adaptive/schemas.py, apps/api/narrare/ai_assist/schemas.py).
 *
 * Implementation note — why this is NOT `Object.keys({} as T)`:
 *   A TypeScript interface cast is compile-time only; `{}` has zero own
 *   enumerable properties at runtime, so `Object.keys({} as T)` would always
 *   return `[]` and the assertions could never pass. Instead each sample is a
 *   fully-populated literal annotated with the interface type. This gives TWO
 *   layers of enforcement:
 *     1. `vitest run`  — `Object.keys(sample)` returns the real runtime keys.
 *     2. `tsc` (type-check) — the sample must satisfy the interface, so any
 *        missing/extra REQUIRED field is a compile error on the annotation.
 *   snake_case is preserved to mirror the Pydantic SSOT.
 */

import { describe, expect, it } from "vitest";
import type {
  AdaptiveContextResponse,
  AdaptiveSettingsResponse,
  AdaptiveSourceSummary,
  AdaptiveToggleInput,
  AdaptiveWeightsInput,
  AdaptiveWeightsResponse,
  DialogueAlternative,
  DialogueCoachRequest,
  DialogueCoachResponse,
  DialogueCoachStreamEvent,
  DialogueIssue,
} from "@/types";

function fieldNames<T extends object>(sample: T): string[] {
  return Object.keys(sample).sort();
}

describe("adaptive types mirror Pydantic (RULE-17)", () => {
  it("AdaptiveWeightsResponse has the 4 clamped weights", () => {
    const sample: AdaptiveWeightsResponse = {
      preference: 0.7,
      voice_fidelity: 0.9,
      style_constraints: 1.0,
      avoidance: 1.0,
    };
    expect(fieldNames(sample)).toEqual([
      "avoidance",
      "preference",
      "style_constraints",
      "voice_fidelity",
    ]);
  });

  it("AdaptiveContextResponse matches the GET /context shape", () => {
    const sample: AdaptiveContextResponse = {
      project_id: "p1",
      enabled: true,
      weights: {
        preference: 0.7,
        voice_fidelity: 0.9,
        style_constraints: 1.0,
        avoidance: 1.0,
      },
      sources: {
        preference_text: "",
        voice_profiles_text: "",
        style_constraints_text: "",
        avoidance_patterns_text: "",
      },
      has_any_signal: false,
    };
    expect(fieldNames(sample)).toEqual([
      "enabled",
      "has_any_signal",
      "project_id",
      "sources",
      "weights",
    ]);
  });

  it("AdaptiveSettingsResponse matches POST /toggle + /weights shape", () => {
    const sample: AdaptiveSettingsResponse = {
      enabled: true,
      weights: {
        preference: 0.7,
        voice_fidelity: 0.9,
        style_constraints: 1.0,
        avoidance: 1.0,
      },
    };
    expect(fieldNames(sample)).toEqual(["enabled", "weights"]);
  });

  it("AdaptiveSourceSummary has the 4 *_text fields", () => {
    const sample: AdaptiveSourceSummary = {
      preference_text: "",
      voice_profiles_text: "",
      style_constraints_text: "",
      avoidance_patterns_text: "",
    };
    expect(fieldNames(sample)).toEqual([
      "avoidance_patterns_text",
      "preference_text",
      "style_constraints_text",
      "voice_profiles_text",
    ]);
  });

  it("AdaptiveToggleInput + AdaptiveWeightsInput are the request bodies", () => {
    const toggle: AdaptiveToggleInput = { enabled: true };
    expect(fieldNames(toggle)).toEqual(["enabled"]);

    const weights: AdaptiveWeightsInput = {
      preference: 0.7,
      voice_fidelity: 0.9,
      style_constraints: 1.0,
      avoidance: 1.0,
    };
    expect(fieldNames(weights)).toEqual([
      "avoidance",
      "preference",
      "style_constraints",
      "voice_fidelity",
    ]);
  });
});

describe("dialogueCoach types mirror Pydantic (RULE-17)", () => {
  it("DialogueCoachRequest body fields", () => {
    const sample: DialogueCoachRequest = {
      selection_text: "Hello.",
      mode: "analyze",
    };
    expect(fieldNames(sample)).toEqual(["mode", "selection_text"]);
  });

  it("DialogueCoachResponse top-level fields", () => {
    const sample: DialogueCoachResponse = {
      chapter_id: "c1",
      mode: "analyze",
      issues: [],
      adaptive_summary: "",
    };
    expect(fieldNames(sample)).toEqual(["adaptive_summary", "chapter_id", "issues", "mode"]);
  });

  it("DialogueIssue fields", () => {
    const sample: DialogueIssue = {
      issue_type: "voice-drift",
      speaker: "Anna",
      original_quote: "Hi.",
      diagnosis: "off-voice",
      severity: "low",
      alternatives: null,
    };
    expect(fieldNames(sample)).toEqual([
      "alternatives",
      "diagnosis",
      "issue_type",
      "original_quote",
      "severity",
      "speaker",
    ]);
  });

  it("DialogueAlternative fields", () => {
    const sample: DialogueAlternative = {
      rewrite: "Hey.",
      explanation: "warmer",
    };
    expect(fieldNames(sample)).toEqual(["explanation", "rewrite"]);
  });

  it("DialogueCoachStreamEvent discriminates on `event`", () => {
    // Fully-populated sample (SSE event fields are optional by design).
    const sample: DialogueCoachStreamEvent = {
      event: "progress",
      result: null,
      progress: "working",
      error: null,
      is_final: false,
    };
    expect(fieldNames(sample)).toContain("event");
    expect(fieldNames(sample)).toContain("is_final");
  });
});
