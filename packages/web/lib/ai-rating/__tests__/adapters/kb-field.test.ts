/**
 * kbFieldSuggestRatingAdapter tests — KB field suggestion → AIRatingViewModel (CR-AUFG-07-24 Task 11).
 */

import { describe, expect, it } from "vitest";
import { kbFieldSuggestRatingAdapter } from "@/lib/ai-rating/adapters/kb-field";
import type { KBCreationField } from "@/lib/api/kb-sessions";

const field: KBCreationField = {
  field_key: "personality",
  label: "Personality",
  field_type: "text",
  required: false,
  source: "ai",
  ai_suggested_value: "Brave and cunning",
  ai_reasoning: "adds depth",
  user_value: undefined,
  final_value: undefined,
};

describe("kbFieldSuggestRatingAdapter", () => {
  it("builds an AIRatingViewModel tagged kb_field_suggest", () => {
    const vm = kbFieldSuggestRatingAdapter({
      field,
      projectId: "proj-1",
      action: "accept",
    });
    if (vm === null) throw new Error("expected rating view model");
    expect(vm.sourceType).toBe("kb_field_suggest");
    expect(vm.sourceId).toBe("personality");
    expect(vm.intent).toBe("kb_field_suggest");
    expect(vm.suggestionText).toBe("Brave and cunning");
    expect(vm.action).toBe("accept");
    expect(vm.chapterId).toBeNull();
    expect(vm.projectId).toBe("proj-1");
    expect(vm.genre).toBeNull();
    expect(vm.mode).toBeNull();
  });

  it("passes the reject action through unchanged", () => {
    const vm = kbFieldSuggestRatingAdapter({
      field,
      projectId: "proj-1",
      action: "reject",
    });
    if (vm === null) throw new Error("expected rating view model");
    expect(vm.action).toBe("reject");
  });

  it("returns null for an empty field_key", () => {
    const vm = kbFieldSuggestRatingAdapter({
      field: { ...field, field_key: "  " },
      projectId: "proj-1",
      action: "accept",
    });
    expect(vm).toBeNull();
  });

  it("falls through to empty string when ai_suggested_value is undefined", () => {
    const vm = kbFieldSuggestRatingAdapter({
      field: { ...field, ai_suggested_value: undefined },
      projectId: "proj-1",
      action: "accept",
    });
    expect(vm).toBeNull();
  });
});
