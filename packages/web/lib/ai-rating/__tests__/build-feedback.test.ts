/**
 * buildFeedbackRequest tests (CR-AUFG-07-24).
 *
 * Verifies the single source-of-truth payload builder maps an
 * AIRatingViewModel + rating into a POST /memory/feedback body with the
 * invariants:
 *   - `source_type` present (non-null) for typed sources, absent for legacy null
 *   - `rating_reason` lands in `context` (privacy-safe), never top-level
 *   - out-of-range ratings throw at build time
 */

import { describe, expect, it } from "vitest";
import { buildFeedbackRequest } from "../build-feedback";
import type { AIRatingViewModel } from "../contracts";

const vm: AIRatingViewModel = {
  sourceType: "chat_message",
  sourceId: "msg-42",
  projectId: "proj-1",
  intent: "chat_assistant",
  suggestionText: "Here is a paragraph.",
  action: "accept",
  chapterId: "ch-9",
  genre: null,
  mode: null,
};

describe("buildFeedbackRequest", () => {
  it("builds a FeedbackRequest with source_id, source_type, and rating", () => {
    const req = buildFeedbackRequest(vm, { rating: 5 });
    expect(req.action).toBe("accept");
    expect(req.source_id).toBe("msg-42");
    expect(req.source_type).toBe("chat_message");
    expect(req.intent).toBe("chat_assistant");
    expect(req.suggestion_text).toBe("Here is a paragraph.");
    expect(req.rating).toBe(5);
    expect(req.project_id).toBe("proj-1");
    expect(req.chapter_id).toBe("ch-9");
  });

  it("routes a non-UUID sourceId into source_id and NEVER suggestion_id (CR-AUFG-07-24 contract)", () => {
    // Regression for the CR-AUFG-07-24 blocker: the old builder mapped
    // vm.sourceId straight onto suggestion_id. For non-UUID surface ids
    // (change-7, msg-42, field keys, numeric ids) this produced an invalid
    // suggestion_id that the backend (uuid.UUID | None) now rejects. The
    // canonical UUID is derived server-side from (source_id, source_type);
    // the frontend must forward the raw id as source_id only.
    const req = buildFeedbackRequest(vm, { rating: 4 });
    expect(req.source_id).toBe("msg-42");
    expect(req.source_type).toBe("chat_message");
    expect(req.suggestion_id).toBeUndefined();
  });

  it("forwards a valid UUID sourceId as suggestion_id (back-compat for real UUIDs)", () => {
    // When the surface genuinely owns a UUID suggestion id, it is still valid
    // to forward it as suggestion_id. The builder additionally keeps
    // source_id populated so the backend contract (either suggestion_id OR
    // source_id+source_type) is satisfied either way.
    const uuidVm: AIRatingViewModel = {
      ...vm,
      sourceId: "11111111-2222-3333-4444-555555555555",
    };
    const req = buildFeedbackRequest(uuidVm, { rating: 5 });
    expect(req.suggestion_id).toBe("11111111-2222-3333-4444-555555555555");
    expect(req.source_id).toBe("11111111-2222-3333-4444-555555555555");
    expect(req.source_type).toBe("chat_message");
  });

  it("omits rating_reason key when no reason is provided", () => {
    const req = buildFeedbackRequest(vm, { rating: 5 });
    expect(req.context).toEqual({});
  });

  it("includes rating_reason in context when provided", () => {
    const req = buildFeedbackRequest(vm, { rating: 2, reason: "too long" });
    expect(req.context).toEqual({ rating_reason: "too long" });
  });

  it("trims whitespace-only reasons to an empty context", () => {
    const req = buildFeedbackRequest(vm, { rating: 3, reason: "   " });
    expect(req.context).toEqual({});
  });

  it("maps the vm action through unchanged (accept/modify/reject)", () => {
    const acceptReq = buildFeedbackRequest({ ...vm, action: "accept" }, { rating: 3 });
    const modifyReq = buildFeedbackRequest({ ...vm, action: "modify" }, { rating: 3 });
    expect(acceptReq.action).toBe("accept");
    expect(modifyReq.action).toBe("modify");
  });

  it("rejects rating above 5 at build time (runtime guard)", () => {
    expect(() => buildFeedbackRequest(vm, { rating: 6 as unknown as 1 })).toThrow(/rating.*1.*5/i);
  });

  it("rejects rating below 1 at build time (runtime guard)", () => {
    expect(() => buildFeedbackRequest(vm, { rating: 0 as unknown as 1 })).toThrow(/rating.*1.*5/i);
  });

  it("rejects non-integer rating at build time", () => {
    expect(() => buildFeedbackRequest(vm, { rating: 3.5 as unknown as 1 })).toThrow(/rating/i);
  });

  it("omits source_type when vm provides null (legacy back-compat guard)", () => {
    // The contract types sourceType as FeedbackSourceType (non-null). We still
    // guard the builder so an accidental null becomes a missing key, not a
    // backend 422 validation error.
    // @ts-expect-error — deliberately invalid for the runtime guard test
    const req = buildFeedbackRequest({ ...vm, sourceType: null }, { rating: 4 });
    expect(req.source_type).toBeUndefined();
  });

  it("always produces a defined context object (never undefined)", () => {
    const req = buildFeedbackRequest(vm, { rating: 1 });
    expect(req.context).toBeDefined();
    expect(typeof req.context).toBe("object");
  });
});
