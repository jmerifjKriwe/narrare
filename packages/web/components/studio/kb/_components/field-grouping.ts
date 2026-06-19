/**
 * Field grouping helpers for the KB session field list.
 *
 * Partitions creation-session fields into display groups by status:
 * empty (needs input), AI suggestions pending review, user-filled, and
 * merged / world-derived.
 *
 * Extracted from KBSessionFieldList for RULE-04 compliance (one
 * responsibility per file: field-status partitioning).
 */

import type { KBCreationField } from "@/lib/api/kb-sessions";

/** Display groups produced by {@link groupFieldsByStatus}. */
export interface FieldGroups {
  empty: KBCreationField[];
  ai: KBCreationField[];
  user: KBCreationField[];
  merged: KBCreationField[];
}

/** Whether a field counts as "filled" for progress display. */
export function isFieldFilled(field: KBCreationField): boolean {
  return Boolean(field.final_value || field.user_value || field.ai_suggested_value);
}

/** Partition session fields into display groups by source/status. */
export function groupFieldsByStatus(fields: KBCreationField[]): FieldGroups {
  return {
    empty: fields.filter((f) => !f.final_value && !f.user_value && !f.ai_suggested_value),
    ai: fields.filter((f) => f.ai_suggested_value && f.source === "ai"),
    user: fields.filter((f) => (f.user_value || f.final_value) && f.source === "user"),
    merged: fields.filter((f) => f.source === "merged" || f.source === "world_derived"),
  };
}
