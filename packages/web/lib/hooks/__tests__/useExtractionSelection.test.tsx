/**
 * useExtractionSelection hook tests — Pure React state for extraction items.
 *
 * Tests useExtractionSelection hook:
 * 1. loadResults sorts items by confidence and selects all
 * 2. toggleItem deselects a selected item
 * 3. toggleItem re-selects a deselected item
 * 4. selectAll selects all items
 * 5. selectNone deselects all items
 * 6. loadResults replaces previous state
 * 7. loadResults stores analysis notes
 */

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ExtractionItem } from "@/lib/api/extraction";
import { useExtractionSelection } from "@/lib/hooks/useExtractionSelection";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const items: ExtractionItem[] = [
  {
    item_type: "new_entity",
    entity_type: "character",
    name: "Anna Schmidt",
    confidence: 0.92,
    source_text: "She walked through the old archive.",
    proposed_content: { role: "Protagonist" },
    target_entity_id: null,
    conflict_description: null,
    relationship_type: null,
    related_entity_name: null,
  },
  {
    item_type: "new_entity",
    entity_type: "location",
    name: "Old Archive",
    confidence: 0.85,
    source_text: "the old archive",
    proposed_content: { type: "building" },
    target_entity_id: null,
    conflict_description: null,
    relationship_type: null,
    related_entity_name: null,
  },
  {
    item_type: "new_entity",
    entity_type: "character",
    name: "Dr. Weber",
    confidence: 0.97,
    source_text: "Dr. Weber examined the documents.",
    proposed_content: { role: "Mentor" },
    target_entity_id: null,
    conflict_description: null,
    relationship_type: null,
    related_entity_name: null,
  },
];

const unsortedOutput = {
  results: [items[0], items[2], items[1]], // intentionally not sorted
  analysis_notes: "Extracted 3 entities from chapter.",
};

const secondOutput = {
  results: [
    {
      item_type: "relationship" as const,
      entity_type: null,
      name: "Anna → Archive",
      confidence: 0.75,
      source_text: "She explored the archive.",
      proposed_content: null,
      target_entity_id: null,
      conflict_description: null,
      relationship_type: "visits",
      related_entity_name: "Old Archive",
    },
  ],
  analysis_notes: "Found 1 relationship.",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useExtractionSelection", () => {
  it("loadResults sorts items by confidence descending and selects all", () => {
    const { result } = renderHook(() => useExtractionSelection());

    act(() => {
      result.current.loadResults(unsortedOutput);
    });

    // Items should be sorted by confidence descending
    expect(result.current.items).toHaveLength(3);
    expect(result.current.items[0].name).toBe("Dr. Weber"); // 0.97
    expect(result.current.items[1].name).toBe("Anna Schmidt"); // 0.92
    expect(result.current.items[2].name).toBe("Old Archive"); // 0.85

    // All items should be selected
    expect(result.current.selectedIndices.size).toBe(3);
    expect(result.current.selectedIndices.has(0)).toBe(true);
    expect(result.current.selectedIndices.has(1)).toBe(true);
    expect(result.current.selectedIndices.has(2)).toBe(true);
  });

  it("loadResults stores analysis notes", () => {
    const { result } = renderHook(() => useExtractionSelection());

    act(() => {
      result.current.loadResults(unsortedOutput);
    });

    expect(result.current.analysisNotes).toBe("Extracted 3 entities from chapter.");
  });

  it("toggleItem deselects a selected item", () => {
    const { result } = renderHook(() => useExtractionSelection());

    act(() => {
      result.current.loadResults(unsortedOutput);
    });

    expect(result.current.selectedIndices.size).toBe(3);

    act(() => {
      result.current.toggleItem(1);
    });

    expect(result.current.selectedIndices.size).toBe(2);
    expect(result.current.selectedIndices.has(0)).toBe(true);
    expect(result.current.selectedIndices.has(1)).toBe(false);
    expect(result.current.selectedIndices.has(2)).toBe(true);
  });

  it("toggleItem re-selects a deselected item", () => {
    const { result } = renderHook(() => useExtractionSelection());

    act(() => {
      result.current.loadResults(unsortedOutput);
    });

    act(() => {
      result.current.toggleItem(0);
    });

    expect(result.current.selectedIndices.has(0)).toBe(false);

    act(() => {
      result.current.toggleItem(0);
    });

    expect(result.current.selectedIndices.has(0)).toBe(true);
    expect(result.current.selectedIndices.size).toBe(3);
  });

  it("selectAll selects all items", () => {
    const { result } = renderHook(() => useExtractionSelection());

    act(() => {
      result.current.loadResults(unsortedOutput);
    });

    // Deselect all first
    act(() => {
      result.current.selectNone();
    });

    expect(result.current.selectedIndices.size).toBe(0);

    // Select all
    act(() => {
      result.current.selectAll();
    });

    expect(result.current.selectedIndices.size).toBe(3);
    expect(result.current.selectedIndices.has(0)).toBe(true);
    expect(result.current.selectedIndices.has(1)).toBe(true);
    expect(result.current.selectedIndices.has(2)).toBe(true);
  });

  it("selectNone deselects all items", () => {
    const { result } = renderHook(() => useExtractionSelection());

    act(() => {
      result.current.loadResults(unsortedOutput);
    });

    act(() => {
      result.current.selectNone();
    });

    expect(result.current.selectedIndices.size).toBe(0);
  });

  it("loadResults replaces previous state", () => {
    const { result } = renderHook(() => useExtractionSelection());

    // Load initial results
    act(() => {
      result.current.loadResults(unsortedOutput);
    });

    expect(result.current.items).toHaveLength(3);
    expect(result.current.analysisNotes).toBe("Extracted 3 entities from chapter.");

    // Load new results (fewer items)
    act(() => {
      result.current.loadResults(secondOutput);
    });

    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].name).toBe("Anna → Archive");
    expect(result.current.selectedIndices.size).toBe(1); // all selected by default
    expect(result.current.analysisNotes).toBe("Found 1 relationship.");
  });
});
