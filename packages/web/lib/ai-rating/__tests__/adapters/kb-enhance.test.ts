/**
 * kbEnhanceRatingAdapter tests — KB enhancement → AIRatingViewModel (CR-AUFG-07-24 Task 9).
 */

import { describe, expect, it } from "vitest";
import { kbEnhanceRatingAdapter } from "@/lib/ai-rating/adapters/kb-enhance";
import type { KBEnhancementResult } from "@/lib/api/kb-sessions";

const enhancement: KBEnhancementResult = {
  field_key: "role",
  original: "Mentor",
  suggested: "Wise mentor",
  reasoning: "more evocative",
};

describe("kbEnhanceRatingAdapter", () => {
  it("builds an AIRatingViewModel tagged kb_enhance_field", () => {
    const vm = kbEnhanceRatingAdapter({
      enhancement,
      projectId: "proj-1",
      fieldLabel: "Role",
      action: "accept",
    });
    if (vm === null) throw new Error("expected rating view model");
    expect(vm.sourceType).toBe("kb_enhance_field");
    expect(vm.sourceId).toBe("role");
    expect(vm.intent).toBe("kb_enhance");
    expect(vm.suggestionText).toBe("Wise mentor");
    expect(vm.action).toBe("accept");
    expect(vm.chapterId).toBeNull();
    expect(vm.projectId).toBe("proj-1");
    expect(vm.genre).toBeNull();
    expect(vm.mode).toBeNull();
  });

  it("passes the reject action through unchanged", () => {
    const vm = kbEnhanceRatingAdapter({
      enhancement,
      projectId: "proj-1",
      fieldLabel: "Role",
      action: "reject",
    });
    if (vm === null) throw new Error("expected rating view model");
    expect(vm.action).toBe("reject");
  });
});
