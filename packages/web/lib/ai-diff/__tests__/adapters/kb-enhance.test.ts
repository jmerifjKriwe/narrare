import { describe, expect, it } from "vitest";
import type { KBEnhancementResult } from "@/lib/api/kb-sessions";
import { kbEnhanceFieldAdapter } from "../../adapters/kb-enhance";

const enhancement: KBEnhancementResult = {
  field_key: "role",
  original: "Mentor",
  suggested: "Wise mentor and guide",
  reasoning: "Adds depth",
};

describe("kbEnhanceFieldAdapter", () => {
  it("builds a FIELD-mode view model (no inline prose diff)", () => {
    const vm = kbEnhanceFieldAdapter(enhancement, "Role");
    expect(vm.mode).toBe("field");
    expect(vm.id).toBe("role");
    expect(vm.originalFull).toBe("Mentor");
    expect(vm.suggestedFull).toBe("Wise mentor and guide");
    expect(vm.label).toBe("Role");
  });

  it("NEVER produces inline segments (structured fields are not prose diffs)", () => {
    const vm = kbEnhanceFieldAdapter(enhancement, "Role");
    expect(vm.segments).toEqual([]);
  });
});
