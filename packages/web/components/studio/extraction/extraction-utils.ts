/**
 * extraction-utils — Pure helpers for KB extraction phase management.
 *
 * Extracted from useExtractionPhase to keep the hook under the 150-line
 * hard limit (RULE-04). All functions are stateless and testable in isolation.
 */

import type { ApplyExtractionItem, ExtractionItem } from "@/lib/api/extraction";

// --- Types ---

export type ExtractionPhase = "loading" | "review" | "applying" | "done" | "error";

// --- Error handling ---

/** Check if an error represents a user-initiated abort (not a real error). */
export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

/** Extract user-visible message from an error, preferring structured AIErrorResponse. */
export function getErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error && "userMessage" in err) {
    return (err as { userMessage: string }).userMessage;
  }
  return err instanceof Error ? err.message : fallback;
}

/**
 * Shared error handler for extraction mutation catches (mount effect + retry).
 * Handles abort → close, otherwise marks connection lost and shows error.
 */
export function handleExtractionError(
  err: unknown,
  fallbackMsg: string,
  actions: {
    onClose: () => void;
    markConnectionLost: () => void;
    setErrorMsg: (msg: string) => void;
    setPhase: (phase: ExtractionPhase) => void;
  },
): void {
  if (isAbortError(err)) {
    actions.onClose();
    return;
  }
  actions.markConnectionLost();
  actions.setErrorMsg(getErrorMessage(err, fallbackMsg));
  actions.setPhase("error");
}

// --- Data transformation ---

/** Map selected extraction items to the apply API payload shape. */
export function mapSelectedItems(
  items: readonly ExtractionItem[],
  selectedIndices: ReadonlySet<number>,
): ApplyExtractionItem[] {
  return items
    .filter((_, idx) => selectedIndices.has(idx))
    .map((item) => ({
      item_type: item.item_type,
      name: item.name,
      entity_type: item.entity_type,
      proposed_content: item.proposed_content,
      target_entity_id: item.target_entity_id,
      relationship_type: item.relationship_type,
      related_entity_name: item.related_entity_name,
      source_text: item.source_text,
    }));
}
