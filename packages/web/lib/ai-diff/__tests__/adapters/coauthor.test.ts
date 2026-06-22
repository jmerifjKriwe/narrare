import { describe, expect, it } from "vitest";
import type { ChangeDetail } from "@/lib/api/coauthor";
import { coAuthorChangeAdapter } from "../../adapters/coauthor";

const change: ChangeDetail = {
  id: "ch-1",
  change_type: "word_choice",
  original_text: "quick",
  revised_text: "swift",
  index: 0,
};

describe("coAuthorChangeAdapter", () => {
  it("maps a ChangeDetail to a text-mode view model", () => {
    const vm = coAuthorChangeAdapter(change);
    expect(vm.id).toBe("ch-1");
    expect(vm.mode).toBe("text");
    expect(vm.originalFull).toBe("quick");
    expect(vm.suggestedFull).toBe("swift");
    expect(vm.label).toBe("word_choice");
    expect(vm.provisional).toBe(false);
  });

  it("segments the original->revised text", () => {
    const vm = coAuthorChangeAdapter(change);
    expect(vm.segments.some((s) => s.kind === "removed")).toBe(true);
    expect(vm.segments.some((s) => s.kind === "added")).toBe(true);
  });
});
