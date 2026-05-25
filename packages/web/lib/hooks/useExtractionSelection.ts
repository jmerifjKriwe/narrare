"use client";

/**
 * useExtractionSelection — Manages extraction item selection state.
 *
 * Handles: items storage, selected indices, select all/none/toggle,
 * and sorting by confidence on result arrival.
 */

import { useCallback, useState } from "react";
import type { ExtractionItem } from "@/lib/api/extraction";

export function useExtractionSelection() {
  const [items, setItems] = useState<ExtractionItem[]>([]);
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(new Set());
  const [analysisNotes, setAnalysisNotes] = useState("");

  const loadResults = useCallback(
    (output: { results: ExtractionItem[]; analysis_notes: string }) => {
      const sorted = [...output.results].sort((a, b) => b.confidence - a.confidence);
      setItems(sorted);
      setAnalysisNotes(output.analysis_notes);
      setSelectedIndices(new Set(sorted.map((_, i) => i)));
    },
    [],
  );

  const toggleItem = useCallback((idx: number) => {
    setSelectedIndices((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIndices(new Set(items.map((_, i) => i)));
  }, [items]);

  const selectNone = useCallback(() => {
    setSelectedIndices(new Set());
  }, []);

  return {
    items,
    selectedIndices,
    analysisNotes,
    loadResults,
    toggleItem,
    selectAll,
    selectNone,
  };
}
