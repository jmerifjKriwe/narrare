import type { KBEnhancementResult } from "@/lib/api/kb-sessions";
import type { AIDiffViewModel } from "../contracts";

/**
 * Map a KB enhancement to a FIELD-mode {@link AIDiffViewModel}.
 *
 * Structured fields are compared as whole values (before/after), NEVER as an
 * inline prose diff — per CR-AUFG-07-18 AC #3. Invariant: `segments` is empty.
 *
 * `fieldLabel` is nullable: pass the label when the surrounding context does
 * NOT already render it (so AIDiffView's header shows it); pass `null` when the
 * caller already displays the field name (e.g. the KB card header) to avoid a
 * duplicate label (RULE-06 single responsibility, no redundant UI).
 */
export function kbEnhanceFieldAdapter(
  enhancement: KBEnhancementResult,
  fieldLabel: string | null,
): AIDiffViewModel {
  return {
    id: enhancement.field_key,
    mode: "field",
    segments: [],
    originalFull: enhancement.original,
    suggestedFull: enhancement.suggested,
    label: fieldLabel,
    provisional: false,
  };
}
