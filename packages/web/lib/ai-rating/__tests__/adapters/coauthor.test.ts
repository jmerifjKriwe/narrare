/**
 * coAuthorRatingAdapter tests — Co-Author change → AIRatingViewModel (CR-AUFG-07-24 Task 8).
 */

import { describe, expect, it } from "vitest";
import { coAuthorRatingAdapter } from "@/lib/ai-rating/adapters/coauthor";
import type { ChangeDetail } from "@/lib/api/coauthor";

const change: ChangeDetail = {
  id: "change-7",
  index: 6,
  original_text: "He ran fast.",
  revised_text: "He sprinted.",
  change_type: "rephrase",
};

describe("coAuthorRatingAdapter", () => {
  it("builds an AIRatingViewModel tagged co_author_change", () => {
    const vm = coAuthorRatingAdapter({
      change,
      projectId: "proj-1",
      chapterId: "ch-1",
      action: "accept",
    });
    if (vm === null) throw new Error("expected rating view model");
    expect(vm.sourceType).toBe("co_author_change");
    expect(vm.sourceId).toBe("change-7");
    expect(vm.intent).toBe("co_author");
    expect(vm.suggestionText).toBe("He sprinted.");
    expect(vm.action).toBe("accept");
    expect(vm.chapterId).toBe("ch-1");
    expect(vm.projectId).toBe("proj-1");
    expect(vm.genre).toBeNull();
    expect(vm.mode).toBeNull();
  });

  it("passes the reject action through unchanged", () => {
    const vm = coAuthorRatingAdapter({
      change,
      projectId: "proj-1",
      chapterId: "ch-1",
      action: "reject",
    });
    if (vm === null) throw new Error("expected rating view model");
    expect(vm.action).toBe("reject");
  });

  it("accepts a null chapterId", () => {
    const vm = coAuthorRatingAdapter({
      change,
      projectId: "proj-1",
      chapterId: null,
      action: "accept",
    });
    if (vm === null) throw new Error("expected rating view model");
    expect(vm.chapterId).toBeNull();
  });

  it("returns null for an empty source id (whitespace)", () => {
    const vm = coAuthorRatingAdapter({
      change: { ...change, id: "  " },
      projectId: "proj-1",
      chapterId: null,
      action: "accept",
    });
    expect(vm).toBeNull();
  });
});
