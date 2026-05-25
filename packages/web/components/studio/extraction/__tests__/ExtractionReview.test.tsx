/**
 * ExtractionReview tests — Results list with bulk actions.
 *
 * Tests:
 * 1. Renders list of item cards
 * 2. Shows results summary with count
 * 3. Select all / select none buttons work
 * 4. Analysis notes section renders when present
 * 5. Empty results shows no item cards
 * 6. Select all calls onSelectAll
 * 7. Select none calls onSelectNone
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExtractionReview } from "@/components/studio/extraction/ExtractionReview";
import type { ExtractionItem } from "@/lib/api/extraction";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeItem(overrides: Partial<ExtractionItem> = {}): ExtractionItem {
  return {
    item_type: "new_entity",
    entity_type: "character",
    name: "Anna Schmidt",
    confidence: 0.92,
    source_text: "She walked through the old archive.",
    proposed_content: null,
    target_entity_id: null,
    conflict_description: null,
    relationship_type: null,
    related_entity_name: null,
    ...overrides,
  };
}

const sampleItems: ExtractionItem[] = [
  makeItem({ name: "Anna Schmidt", confidence: 0.92 }),
  makeItem({ name: "Dr. Viktor Stein", confidence: 0.85, item_type: "update_entity" }),
  makeItem({
    name: "Anna Schmidt",
    confidence: 0.7,
    item_type: "relationship",
    related_entity_name: "The Old Archive",
    relationship_type: "frequents",
  }),
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ExtractionReview", () => {
  it("renders list of item cards", () => {
    render(
      <ExtractionReview
        items={sampleItems}
        selectedIndices={new Set([0, 1, 2])}
        onToggleItem={vi.fn()}
        onSelectAll={vi.fn()}
        onSelectNone={vi.fn()}
        analysisNotes=""
      />,
    );

    // Each item card shows its name
    expect(screen.getByText("Anna Schmidt")).toBeDefined();
    expect(screen.getByText("Dr. Viktor Stein")).toBeDefined();
  });

  it("shows results summary with count", () => {
    render(
      <ExtractionReview
        items={sampleItems}
        selectedIndices={new Set([0, 1, 2])}
        onToggleItem={vi.fn()}
        onSelectAll={vi.fn()}
        onSelectNone={vi.fn()}
        analysisNotes=""
      />,
    );

    // The i18n mock returns "kb.extractionResultsSummary" with {count} replaced by 3
    expect(screen.getByText("kb.extractionResultsSummary")).toBeDefined();
  });

  it("calls onSelectAll when 'Select All' button is clicked", () => {
    const onSelectAll = vi.fn();

    render(
      <ExtractionReview
        items={sampleItems}
        selectedIndices={new Set([0])}
        onToggleItem={vi.fn()}
        onSelectAll={onSelectAll}
        onSelectNone={vi.fn()}
        analysisNotes=""
      />,
    );

    fireEvent.click(screen.getByText("kb.extractionSelectAll"));
    expect(onSelectAll).toHaveBeenCalledTimes(1);
  });

  it("calls onSelectNone when 'Select None' button is clicked", () => {
    const onSelectNone = vi.fn();

    render(
      <ExtractionReview
        items={sampleItems}
        selectedIndices={new Set([0, 1, 2])}
        onToggleItem={vi.fn()}
        onSelectAll={vi.fn()}
        onSelectNone={onSelectNone}
        analysisNotes=""
      />,
    );

    fireEvent.click(screen.getByText("kb.extractionSelectNone"));
    expect(onSelectNone).toHaveBeenCalledTimes(1);
  });

  it("renders analysis notes section when present", () => {
    render(
      <ExtractionReview
        items={sampleItems}
        selectedIndices={new Set([0, 1, 2])}
        onToggleItem={vi.fn()}
        onSelectAll={vi.fn()}
        onSelectNone={vi.fn()}
        analysisNotes="The chapter introduces two main characters and a key location."
      />,
    );

    // Analysis notes section should be visible (collapsed by default)
    expect(screen.getByText("AI Analysis Notes")).toBeDefined();
  });

  it("expands analysis notes on click", () => {
    const notes = "The chapter introduces two main characters and a key location.";

    render(
      <ExtractionReview
        items={sampleItems}
        selectedIndices={new Set([0, 1, 2])}
        onToggleItem={vi.fn()}
        onSelectAll={vi.fn()}
        onSelectNone={vi.fn()}
        analysisNotes={notes}
      />,
    );

    // Click to expand notes
    fireEvent.click(screen.getByText("AI Analysis Notes"));

    // Notes content should now be visible
    expect(screen.getByText(notes)).toBeDefined();
  });

  it("does not render analysis notes section when empty", () => {
    render(
      <ExtractionReview
        items={sampleItems}
        selectedIndices={new Set([0, 1, 2])}
        onToggleItem={vi.fn()}
        onSelectAll={vi.fn()}
        onSelectNone={vi.fn()}
        analysisNotes=""
      />,
    );

    expect(screen.queryByText("AI Analysis Notes")).toBeNull();
  });

  it("renders no item cards when items array is empty", () => {
    render(
      <ExtractionReview
        items={[]}
        selectedIndices={new Set()}
        onToggleItem={vi.fn()}
        onSelectAll={vi.fn()}
        onSelectNone={vi.fn()}
        analysisNotes=""
      />,
    );

    // Summary should show count 0
    expect(screen.getByText("kb.extractionResultsSummary")).toBeDefined();

    // No item card names should be present
    expect(screen.queryByText("Anna Schmidt")).toBeNull();
  });

  it("calls onToggleItem when an item card is toggled", () => {
    const onToggleItem = vi.fn();

    render(
      <ExtractionReview
        items={sampleItems}
        selectedIndices={new Set([0, 1, 2])}
        onToggleItem={onToggleItem}
        onSelectAll={vi.fn()}
        onSelectNone={vi.fn()}
        analysisNotes=""
      />,
    );

    // Click on the first item card header to toggle
    const itemButtons = screen
      .getAllByRole("button")
      .filter(
        (btn) =>
          btn.textContent?.includes("Anna Schmidt") ||
          btn.textContent?.includes("Dr. Viktor Stein"),
      );
    fireEvent.click(itemButtons[0]);

    expect(onToggleItem).toHaveBeenCalledWith(0);
  });
});
