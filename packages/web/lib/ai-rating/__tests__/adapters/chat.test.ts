/**
 * chatRatingAdapter tests — Chat assistant message → AIRatingViewModel (CR-AUFG-07-24 Task 12).
 */

import { describe, expect, it } from "vitest";
import { chatRatingAdapter } from "@/lib/ai-rating/adapters/chat";

describe("chatRatingAdapter", () => {
  it("builds an AIRatingViewModel tagged chat_message from a prose block", () => {
    const vm = chatRatingAdapter({
      messageId: "msg-42",
      prose: "Here is a paragraph the assistant produced.",
      projectId: "proj-1",
      action: "accept",
    });
    if (vm === null) throw new Error("expected rating view model");
    expect(vm.sourceType).toBe("chat_message");
    expect(vm.sourceId).toBe("msg-42");
    expect(vm.intent).toBe("chat_assistant");
    expect(vm.suggestionText).toBe("Here is a paragraph the assistant produced.");
    expect(vm.action).toBe("accept");
    expect(vm.chapterId).toBeNull();
    expect(vm.projectId).toBe("proj-1");
    expect(vm.genre).toBeNull();
    expect(vm.mode).toBeNull();
  });

  it("passes the reject action through unchanged", () => {
    const vm = chatRatingAdapter({
      messageId: "msg-42",
      prose: "Some prose.",
      projectId: "proj-1",
      action: "reject",
    });
    if (vm === null) throw new Error("expected rating view model");
    expect(vm.action).toBe("reject");
  });
});
