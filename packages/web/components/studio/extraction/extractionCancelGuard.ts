/**
 * Extraction cancel guard — one-shot idempotent cancel for the KB
 * extraction panel (wave-fix: cancel-during-loading modal reopen).
 *
 * Mechanism this guards against: the panel's cancel handler aborts the
 * in-flight extraction and calls onClose; abort synchronously rejects the
 * pending mutateAsync promise (ai-mutation-adapter's useAbortCallback), and
 * that rejection lands in the hook's mount/retry catch on a microtask AFTER
 * onClose already ran. handleExtractionError maps AbortError → onClose, so
 * onClose fired twice — and the panel's onClose is wired to
 * editorStore.toggleExtractionPanel (a TRUE toggle, EditorOverlays), which
 * flipped the closed modal back open, stuck in "loading" (startedRef
 * prevents a re-fire).
 *
 * Extracted from useExtractionPhase for modularity (RULE-04); pure move of
 * the wave-fix guard, no behavior change. The guard ref stays owned by the
 * hook and is passed in (same shape as continueStream's accumulatedRef).
 *
 * @module extractionCancelGuard
 */

import type { MutableRefObject } from "react";
import { handleExtractionError } from "./extraction-utils";

/** UI actions handleExtractionError may invoke (shape owned by extraction-utils). */
type ExtractionErrorActions = Parameters<typeof handleExtractionError>[2];

/** Inputs for the cancel path — the guard ref stays owned by the calling hook. */
export interface ExtractionCancelParams {
  /** One-shot cancel flag; armed by the first {@link runCancelExtraction} call. */
  readonly cancelledRef: MutableRefObject<boolean>;
  /** Mutation abort: synchronously rejects the pending promise (AbortError). */
  readonly abort: () => void;
  /** Panel close — in production wired to the toggle-shaped store setter. */
  readonly onClose: () => void;
}

/** Inputs for the catch-side rejection path shared by mount effect + retry. */
export interface ExtractionRejectionParams {
  readonly cancelledRef: MutableRefObject<boolean>;
  /** User-visible fallback message for non-abort failures. */
  readonly fallbackMsg: string;
  readonly actions: ExtractionErrorActions;
}

/**
 * Idempotent cancel: the first invocation arms `cancelledRef` and aborts +
 * closes; every later invocation (double-click, exit-animation window) is a
 * no-op, so `onClose` fires exactly once — a toggle-shaped onClose would
 * otherwise re-open the modal.
 */
export function runCancelExtraction({
  cancelledRef,
  abort,
  onClose,
}: ExtractionCancelParams): void {
  if (cancelledRef.current) return;
  cancelledRef.current = true;
  abort();
  onClose();
}

/**
 * Catch-side rejection handler for the extraction mutations: suppresses the
 * post-cancel abort rejection (panel is already closing/closed — surfacing
 * an error or closing again would only re-toggle the modal open), then
 * delegates to handleExtractionError for everything else.
 */
export function handleExtractionRejection(
  err: unknown,
  { cancelledRef, fallbackMsg, actions }: ExtractionRejectionParams,
): void {
  if (cancelledRef.current) return;
  handleExtractionError(err, fallbackMsg, actions);
}
