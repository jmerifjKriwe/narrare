/**
 * CR-AUFG-07-24 — single source of truth for building a FeedbackRequest from
 * an AIRatingViewModel + AIRatingInput. DRY: every adapter goes through this.
 *
 * RULE-06: this module owns ONE responsibility — mapping a rating decision
 * to the POST /memory/feedback payload shape. It has no UI, no lifecycle.
 */

import type { FeedbackRequest } from "@/types";
import type { AIRatingInput, AIRatingScale, AIRatingViewModel } from "./contracts";

/** Validates that n is in the closed 1..5 scale. */
function assertScale(n: number): asserts n is AIRatingScale {
  if (!Number.isInteger(n) || n < 1 || n > 5) {
    throw new Error(`rating must be an integer 1..5 (got ${String(n)})`);
  }
}

/**
 * Build the canonical POST /memory/feedback payload for a rating event.
 *
 * Invariants:
 *   - `source_id` always carries the raw, stable surface id
 *     (`vm.sourceId`); the backend derives the canonical uuid5 server-side
 *     from (`source_id`, `source_type`). The frontend MUST NOT invent a UUID.
 *   - `suggestion_id` is forwarded ONLY when `vm.sourceId` is itself a valid
 *     UUID (back-compat for surfaces that genuinely own a UUID). Non-UUID
 *     surface ids never reach `suggestion_id` — they would fail the backend
 *     `uuid.UUID | None` validation (CR-AUFG-07-24 blocker).
 *   - `source_type` is only set when `vm.sourceType` is non-null.
 *   - `rating_reason` (when provided and non-empty) lands in `context`, never
 *     as a top-level field — privacy-safe and forward-compatible.
 *   - `context` is always a defined object (never undefined/null) so the
 *     backend always sees a JSON object.
 */

// Canonical 8-4-4-4-12 hex form (any version). Mirrors the backend
// `uuid.UUID` acceptance for the `suggestion_id` field.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function buildFeedbackRequest(vm: AIRatingViewModel, input: AIRatingInput): FeedbackRequest {
  assertScale(input.rating);

  const context: Record<string, unknown> = {};
  if (input.reason && input.reason.trim().length > 0) {
    context.rating_reason = input.reason.trim();
  }

  // Only forward a real UUID as suggestion_id; surface-local ids (change-7,
  // msg-42, field keys, numeric ids) travel exclusively as source_id so the
  // backend uuid.UUID | None validation never sees an invalid string.
  const suggestionId = UUID_RE.test(vm.sourceId) ? vm.sourceId : undefined;

  return {
    action: vm.action,
    suggestion_id: suggestionId,
    source_id: vm.sourceId,
    source_type: vm.sourceType ?? undefined,
    intent: vm.intent,
    suggestion_text: vm.suggestionText,
    rating: input.rating,
    context,
    project_id: vm.projectId,
    chapter_id: vm.chapterId,
    genre: vm.genre,
    mode: vm.mode,
  };
}
