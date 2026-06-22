/**
 * CR-AUFG-07-24 — Shared, domain-agnostic AI rating vocabulary.
 *
 * Frontend-only contract (RULE-03): defined BEFORE any component or adapter.
 * The rating primitive is a pure VIEW + a fire-and-forget submit; it never
 * starts AI work and owns no lifecycle beyond its own REST POST.
 *
 * Mirrors the CR-AUFG-07-18 `lib/ai-diff/contracts.ts` shape: contract first,
 * component second, adapters third.
 *
 * RULE-17: the `FeedbackSourceType` union is a 1:1 mirror of the backend
 * `Literal` / core `FeedbackSourceType` StrEnum — kept in sync by
 * `tests/integration/memory/test_feedback_source_type_parity.py`.
 */

import type { FeedbackAction, FeedbackSourceType } from "@/types";

/** Rating control state machine (matches UI affordances). */
export type AIRatingState =
  | "idle" // rating affordance visible, no decision yet
  | "loading" // POST /memory/feedback in flight
  | "success" // backend confirmed
  | "error" // POST failed — user may retry or skip
  | "skipped"; // user dismissed without rating

/** 1..5 inclusive rating scale. */
export type AIRatingScale = 1 | 2 | 3 | 4 | 5;

/**
 * Immutable, surface-agnostic description of "an AI output the user can rate".
 *
 * - `sourceType` is the closed-vocabulary tag (CR-AUFG-07-24 taxonomy).
 * - `sourceId` is the stable per-surface id (change id, field key, message
 *   id, suggestion id, ...) so ratings are never orphaned.
 * - `action` is the user's accept/reject/modify decision on the SAME output;
 *   rating is a follow-up signal that rides alongside, never replaces, the
 *   action. The caller has already recorded the action event if applicable.
 *
 * All fields are `readonly`: the view model is immutable once constructed by
 * an adapter so the rating UI never mutates source data.
 */
export interface AIRatingViewModel {
  readonly sourceType: FeedbackSourceType;
  readonly sourceId: string;
  readonly projectId: string;
  readonly intent: string;
  readonly suggestionText: string;
  readonly action: FeedbackAction;
  readonly chapterId: string | null;
  readonly genre: string | null;
  readonly mode: string | null;
}

/** Caller-supplied rating payload. */
export interface AIRatingInput {
  readonly rating: AIRatingScale;
  readonly reason?: string;
}
