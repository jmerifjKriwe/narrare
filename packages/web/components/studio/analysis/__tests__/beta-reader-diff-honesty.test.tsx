/**
 * Beta Reader diff honesty regression test (CR-AUFG-07-18 Task 16).
 *
 * The current BetaFeedbackItem schema has `suggestion` (prose advice) and
 * `text_excerpt` (a passage) but NO grounded original→revised text pair.
 * Therefore the beta-reader adapter MUST return null for every live item —
 * feedback stays feedback, and no diff is fabricated (RULE-20: no half
 * implementation). BetaReaderPanel.tsx is intentionally NOT modified.
 *
 * This test pins that honesty contract so a future schema change that adds
 * grounded spans is forced to update `isBetaReaderGrounded` + the adapter
 * together (a coordinated RULE-17 change).
 */

import { describe, expect, it } from "vitest";
import {
  betaReaderGroundedAdapter,
  isBetaReaderGrounded,
} from "@/lib/ai-diff/adapters/beta-reader";
import type { BetaFeedbackItem, BetaReaderResponse } from "@/lib/api/analysis";

const feedback: BetaFeedbackItem[] = [
  {
    category: "pacing",
    severity: "moderate",
    location: "para 2",
    title: "Slow",
    description: "Drags.",
    suggestion: "Tighten the prose.",
    text_excerpt: "The long winding road stretched on and on.",
  },
  {
    category: "prose",
    severity: "minor",
    location: null,
    title: "Wordy",
    description: "Verbose.",
    suggestion: null,
    text_excerpt: null,
  },
];

describe("Beta Reader diff honesty (CR-AUFG-07-18)", () => {
  it("produces NO diff view model for any current-schema feedback item", () => {
    for (const item of feedback) {
      expect(betaReaderGroundedAdapter(item)).toBeNull();
    }
  });

  it("isBetaReaderGrounded is false for every current-schema item", () => {
    for (const item of feedback) {
      expect(isBetaReaderGrounded(item)).toBe(false);
    }
  });

  it("returns null even when suggestion + text_excerpt are both present", () => {
    // suggestion is prose advice, NOT a verbatim replacement — must NOT be
    // treated as a grounded revision (fabrication is explicitly out-of-scope).
    const itemWithBoth = feedback[0];
    expect(itemWithBoth.suggestion).not.toBeNull();
    expect(itemWithBoth.text_excerpt).not.toBeNull();
    expect(betaReaderGroundedAdapter(itemWithBoth)).toBeNull();
  });

  it("a full BetaReaderResponse yields zero grounded diffs", () => {
    const response: BetaReaderResponse = {
      novel_id: "n",
      chapter_ids: ["c1"],
      total_word_count: 1000,
      strengths: [],
      feedback,
      questions: [],
      overall: {
        summary: "ok",
        reader_engagement: 5,
        emotional_impact: 5,
        pacing_score: 5,
        prose_quality: 5,
        plot_progression: 5,
        character_development: 5,
      },
      analyzed_at: "2026-06-22T00:00:00Z",
      cache_key: "k",
    };
    const groundedCount = response.feedback
      .map(betaReaderGroundedAdapter)
      .filter((vm) => vm !== null).length;
    expect(groundedCount).toBe(0);
  });
});
