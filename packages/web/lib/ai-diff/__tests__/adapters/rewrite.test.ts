import { describe, expect, it } from "vitest";
import { rewriteAdapter } from "../../adapters/rewrite";

describe("rewriteAdapter", () => {
  it("builds a text-mode view model with segmented diff", () => {
    const vm = rewriteAdapter("the cat", "the dog", "Sentence", false);
    expect(vm.mode).toBe("text");
    expect(vm.originalFull).toBe("the cat");
    expect(vm.suggestedFull).toBe("the dog");
    expect(vm.label).toBe("Sentence");
    expect(vm.provisional).toBe(false);
    expect(vm.segments.some((s) => s.kind === "added")).toBe(true);
    expect(vm.segments.some((s) => s.kind === "removed")).toBe(true);
  });

  it("accepts a null label", () => {
    const vm = rewriteAdapter("a", "b", null, true);
    expect(vm.label).toBeNull();
    expect(vm.provisional).toBe(true);
  });

  it("produces a stable id derived from the suggestion", () => {
    const vm = rewriteAdapter("a", "suggestion text", null, false);
    expect(vm.id).toContain("rewrite-");
  });
});
