"use client";

import { useCallback, useState } from "react";
import type { ChangeDetail, CoAuthorFocus } from "@/lib/api/coauthor";

import { createAcceptanceMap } from "./coauthor-message-utils";

// ---------------------------------------------------------------------------
// Review and focus state
// ---------------------------------------------------------------------------

export function useCoAuthorReviewState() {
  const [selectedFocus, setSelectedFocus] = useState<CoAuthorFocus[]>(["word_choice"]);
  const [changes, setChanges] = useState<ChangeDetail[]>([]);
  const [acceptance, setAcceptance] = useState<Record<string, boolean>>({});

  const toggleFocus = useCallback((value: CoAuthorFocus) => {
    setSelectedFocus((prev) => {
      if (!prev.includes(value)) {
        return [...prev, value];
      }

      if (prev.length <= 1) {
        return prev;
      }

      return prev.filter((focus) => focus !== value);
    });
  }, []);

  const handleAcceptAll = useCallback(() => {
    setAcceptance(createAcceptanceMap(changes, true));
  }, [changes]);

  const handleRejectAll = useCallback(() => {
    setAcceptance(createAcceptanceMap(changes, false));
  }, [changes]);

  const handleToggleChange = useCallback((id: string) => {
    setAcceptance((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  return {
    selectedFocus,
    changes,
    acceptance,
    setChanges,
    setAcceptance,
    toggleFocus,
    handleAcceptAll,
    handleRejectAll,
    handleToggleChange,
  } as const;
}
