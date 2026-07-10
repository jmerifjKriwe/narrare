/**
 * kbImproveRatingAdapter tests — KB improve suggestion → AIRatingViewModel (CR-AUFG-07-24 Task 10).
 */

import { describe, expect, it } from "vitest";
import { kbImproveRatingAdapter } from "@/lib/ai-rating/adapters/kb-improve";
import type { ImproveSuggestion } from "@/lib/api/kb-improve";

const suggestion: ImproveSuggestion = {
  suggestion_id: 12,
  type: "expand",
  target: "backstory",
  description: "Add a motivation for the antagonist.",
  proposed_content: "She wants revenge.",
  confidence: 0.82,
  reasoning: "current text lacks stakes",
  related_entity_id: null,
  related_entity_name: null,
};

describe("kbImproveRatingAdapter", () => {
  it("builds an AIRatingViewModel tagged kb_improve_suggestion", () => {
    const vm = kbImproveRatingAdapter({
      suggestion,
      projectId: "proj-1",
      action: "accept",
    });
    if (vm === null) throw new Error("expected rating view model");
    expect(vm.sourceType).toBe("kb_improve_suggestion");
    expect(vm.sourceId).toBe("12");
    expect(vm.intent).toBe("kb_improve");
    expect(vm.suggestionText).toBe("Add a motivation for the antagonist.");
    expect(vm.action).toBe("accept");
    expect(vm.chapterId).toBeNull();
    expect(vm.projectId).toBe("proj-1");
    expect(vm.genre).toBeNull();
    expect(vm.mode).toBeNull();
  });

  it("passes the reject action through unchanged", () => {
    const vm = kbImproveRatingAdapter({
      suggestion,
      projectId: "proj-1",
      action: "reject",
    });
    if (vm === null) throw new Error("expected rating view model");
    expect(vm.action).toBe("reject");
  });

  it("returns null for an empty description (whitespace only)", () => {
    const vm = kbImproveRatingAdapter({
      suggestion: { ...suggestion, description: "   " },
      projectId: "proj-1",
      action: "accept",
    });
    expect(vm).toBeNull();
  });
});
