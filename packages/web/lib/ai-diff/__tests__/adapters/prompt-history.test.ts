/**
 * Tests for the prompt-history diff adapter (CR-AUFG-07-18 → CR-AUFG-07-19).
 *
 * The adapter projects a ``PromptRevisionCompareResponse`` onto the shared
 * text-mode :interface:`AIDiffViewModel` so :component:`AIDiffView` can render
 * the revision diff with no knowledge of the prompt-history domain (RULE-07:
 * components → lib, never lib → components).
 */
import { describe, expect, it } from "vitest";
import { promptHistoryDiffAdapter } from "@/lib/ai-diff/adapters/prompt-history";
import type { PromptRevisionCompareResponse } from "@/types";

function compare(
  overrides: Partial<PromptRevisionCompareResponse> = {},
): PromptRevisionCompareResponse {
  return {
    prompt_id: "writing/en/new_chapter",
    from_id: "active",
    to_id: "rev-0001",
    from_source: "active",
    to_source: "edit",
    from_content: "You are a helpful assistant.",
    to_content: "You are a brilliant writing assistant.",
    ...overrides,
  };
}

describe("promptHistoryDiffAdapter", () => {
  it("builds a text-mode view model projecting from_content → to_content", () => {
    const vm = promptHistoryDiffAdapter(compare());

    expect(vm.mode).toBe("text");
    expect(vm.originalFull).toBe("You are a helpful assistant.");
    expect(vm.suggestedFull).toBe("You are a brilliant writing assistant.");
  });

  it("segments map the from→to change (insertion present)", () => {
    const vm = promptHistoryDiffAdapter(compare());

    // to_content adds "brilliant writing" → at least one added segment.
    expect(vm.segments.some((s) => s.kind === "added")).toBe(true);
  });

  it("uses a stable id derived from the from/to ids", () => {
    const vm = promptHistoryDiffAdapter(compare());
    expect(vm.id).toContain("active");
    expect(vm.id).toContain("rev-0001");
  });

  it("is never provisional (history is not a streaming operation)", () => {
    const vm = promptHistoryDiffAdapter(compare());
    expect(vm.provisional).toBe(false);
  });

  it("derives a label from the from/to sources", () => {
    const vm = promptHistoryDiffAdapter(compare());
    expect(vm.label).toContain("active");
    expect(vm.label).toContain("edit");
  });

  it("yields an unchanged segment set when contents are identical", () => {
    const vm = promptHistoryDiffAdapter(
      compare({
        from_content: "same",
        to_content: "same",
      }),
    );
    expect(vm.segments.every((s) => s.kind === "unchanged")).toBe(true);
  });
});
