"use client";

/**
 * useEnhanceSelection — selection state for the KB enhance review.
 *
 * Owns the Set<string> of selected field keys and all derived selection
 * actions: toggle, select-all, select-none, apply-selected, per-card
 * accept/reject, and the stable keyboard-shortcut callback.
 *
 * Extracted from KBEnhanceReview for RULE-04 compliance (one
 * responsibility per file: selection state management).
 */

import { useCallback, useState } from "react";
import type { KBCreationSession, KBEnhancementResult } from "@/lib/api/kb-sessions";

/**
 * Manage the selection set for an enhance-review batch.
 *
 * @param enhancements  Current enhancement results (drives select-all).
 * @param session        Creation session (used to resolve field labels).
 * @param onAcceptEnhancement  Parent callback when applying a single field.
 * @param onApplySelected      Parent callback fired after applying all selected.
 */
export function useEnhanceSelection(
  enhancements: KBEnhancementResult[],
  session: KBCreationSession,
  onAcceptEnhancement: (fieldKey: string, value: string) => void,
  onApplySelected: () => void,
) {
  const [selectedFieldKeys, setSelectedFieldKeys] = useState<Set<string>>(new Set());

  function toggleFieldSelection(fieldKey: string) {
    setSelectedFieldKeys((prev) => {
      const next = new Set(prev);
      if (next.has(fieldKey)) {
        next.delete(fieldKey);
      } else {
        next.add(fieldKey);
      }
      return next;
    });
  }

  function selectAll() {
    setSelectedFieldKeys(new Set(enhancements.map((e) => e.field_key)));
  }

  function selectNone() {
    setSelectedFieldKeys(new Set());
  }

  function applySelected() {
    for (const fieldKey of selectedFieldKeys) {
      const enhancement = enhancements.find((e) => e.field_key === fieldKey);
      if (enhancement) {
        onAcceptEnhancement(fieldKey, enhancement.suggested);
      }
    }
    onApplySelected();
  }

  // Stable reference for keyboard-shortcut effect (CR-AUFG-07-13)
  const applySelectedCb = useCallback(applySelected, [
    selectedFieldKeys,
    enhancements,
    onAcceptEnhancement,
    onApplySelected,
  ]);

  function getFieldLabel(fieldKey: string): string {
    return session.fields.find((f) => f.field_key === fieldKey)?.label || fieldKey;
  }

  function handleCardAccept(fieldKey: string) {
    setSelectedFieldKeys((prev) => new Set(prev).add(fieldKey));
  }

  function handleCardReject(fieldKey: string) {
    setSelectedFieldKeys((prev) => {
      const next = new Set(prev);
      next.delete(fieldKey);
      return next;
    });
  }

  return {
    selectedFieldKeys,
    setSelectedFieldKeys,
    toggleFieldSelection,
    selectAll,
    selectNone,
    applySelected,
    applySelectedCb,
    getFieldLabel,
    handleCardAccept,
    handleCardReject,
  };
}
