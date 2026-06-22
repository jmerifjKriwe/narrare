/**
 * Contracts tests for the shared AI rating vocabulary (CR-AUFG-07-24).
 *
 * Pure compile-time/runtime sanity checks for the contract module. The
 * backend-parity invariant lives in
 * `tests/integration/memory/test_feedback_source_type_parity.py` (Task 14).
 */

import { describe, expect, it } from "vitest";
import type { AIRatingInput, AIRatingScale, AIRatingState, AIRatingViewModel } from "../contracts";

describe("AIRating contracts", () => {
  it("AIRatingState covers idle/loading/success/error/skipped", () => {
    const states: AIRatingState[] = ["idle", "loading", "success", "error", "skipped"];
    // compile-time check: every value is assignable to the union
    for (const s of states) {
      expect(typeof s).toBe("string");
    }
    expect(states).toHaveLength(5);
  });

  it("AIRatingScale is exactly 1..5", () => {
    const scale: AIRatingScale[] = [1, 2, 3, 4, 5];
    expect(scale).toHaveLength(5);
    expect(scale).toEqual([1, 2, 3, 4, 5]);
  });

  it("AIRatingViewModel requires every field the UI depends on", () => {
    const vm: AIRatingViewModel = {
      sourceType: "co_author_change",
      sourceId: "change-1",
      projectId: "proj-1",
      intent: "rewrite",
      suggestionText: "A revised sentence.",
      action: "accept",
      chapterId: "ch-1",
      genre: null,
      mode: null,
    };
    expect(vm.sourceType).toBe("co_author_change");
    expect(vm.sourceId).toBe("change-1");
    expect(vm.projectId).toBe("proj-1");
    expect(vm.action).toBe("accept");
  });

  it("AIRatingViewModel accepts every canonical FeedbackSourceType", () => {
    const types = [
      "co_author_change",
      "kb_field_suggest",
      "kb_enhance_field",
      "kb_improve_suggestion",
      "chat_message",
    ] as const;
    for (const sourceType of types) {
      const vm: AIRatingViewModel = {
        sourceType,
        sourceId: "id",
        projectId: "p",
        intent: "i",
        suggestionText: "t",
        action: "accept",
        chapterId: null,
        genre: null,
        mode: null,
      };
      expect(vm.sourceType).toBe(sourceType);
    }
  });

  it("AIRatingInput requires a rating and accepts an optional reason", () => {
    const withoutReason: AIRatingInput = { rating: 5 };
    const withReason: AIRatingInput = { rating: 2, reason: "too long" };
    expect(withoutReason.rating).toBe(5);
    expect(withoutReason.reason).toBeUndefined();
    expect(withReason.reason).toBe("too long");
    expect(withReason.rating).toBe(2);
  });
});
