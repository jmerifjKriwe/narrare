import type { BetaFeedbackItem } from "@/lib/api/analysis";
import type { AIDiffViewModel } from "../contracts";

/**
 * A feedback item is "grounded" ONLY when it carries a verbatim original
 * passage AND a concrete replacement text (a real A->B revision).
 *
 * The current `BetaFeedbackItem` schema has `text_excerpt` (a passage) and
 * `suggestion` (prose advice) — but `suggestion` is NOT a verbatim
 * replacement, so the pair does not form a grounded revision. Therefore
 * `isBetaReaderGrounded` returns `false` for every live item and
 * {@link betaReaderGroundedAdapter} returns `null`: feedback stays feedback,
 * and no diff is fabricated.
 *
 * RULE-20 (no half implementation): returning `null` here is the COMPLETE,
 * honest behaviour for the current data. When the backend later adds explicit
 * original/revised text spans (a coordinated RULE-17 change), update this
 * predicate and the adapter together.
 */
export function isBetaReaderGrounded(_item: BetaFeedbackItem): boolean {
  // No dedicated original/revised text-pair field exists in the schema today.
  return false;
}

/**
 * Convert a beta-reader feedback item to a diff view model, or `null` when the
 * item is not a grounded revision. Callers MUST render `null` as feedback, not
 * as a diff.
 */
export function betaReaderGroundedAdapter(item: BetaFeedbackItem): AIDiffViewModel | null {
  if (!isBetaReaderGrounded(item)) return null;
  // Forward-compatible branch — unreachable for the live schema. When grounded
  // fields are added, build a text-mode view model here from those fields.
  return null;
}
