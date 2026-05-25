/**
 * ExtractionItemCard tests — Single extraction result card.
 *
 * Tests:
 * 1. Renders type badge for each item_type (new_entity, update_entity, relationship, conflict)
 * 2. Shows entity name
 * 3. Shows confidence percentage
 * 4. Shows source text quote (expandable)
 * 5. Checkbox toggles selection
 * 6. Conflict items show warning styling (AlertTriangle icon)
 * 7. Relationship items show "A → B" format
 * 8. Update entity items show "update existing" indicator via badge
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExtractionItemCard } from "@/components/studio/extraction/ExtractionItemCard";
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
    proposed_content: { role: "Protagonist" },
    target_entity_id: null,
    conflict_description: null,
    relationship_type: null,
    related_entity_name: null,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ExtractionItemCard", () => {
  it("renders type badge for new_entity", () => {
    render(
      <ExtractionItemCard
        item={makeItem({ item_type: "new_entity" })}
        isSelected={true}
        onToggle={vi.fn()}
      />,
    );

    expect(screen.getByText("kb.extractionNewEntity")).toBeDefined();
  });

  it("renders type badge for update_entity", () => {
    render(
      <ExtractionItemCard
        item={makeItem({ item_type: "update_entity" })}
        isSelected={true}
        onToggle={vi.fn()}
      />,
    );

    expect(screen.getByText("kb.extractionUpdateEntity")).toBeDefined();
  });

  it("renders type badge for relationship", () => {
    render(
      <ExtractionItemCard
        item={makeItem({
          item_type: "relationship",
          relationship_type: "frequents",
          related_entity_name: "The Old Archive",
        })}
        isSelected={true}
        onToggle={vi.fn()}
      />,
    );

    expect(screen.getByText("kb.extractionRelationship")).toBeDefined();
  });

  it("renders type badge for conflict", () => {
    render(
      <ExtractionItemCard
        item={makeItem({
          item_type: "conflict",
          conflict_description: "Name conflicts with existing entry",
        })}
        isSelected={true}
        onToggle={vi.fn()}
      />,
    );

    expect(screen.getByText("kb.extractionConflict")).toBeDefined();
  });

  it("shows entity name for non-relationship items", () => {
    render(
      <ExtractionItemCard
        item={makeItem({ name: "Anna Schmidt" })}
        isSelected={true}
        onToggle={vi.fn()}
      />,
    );

    expect(screen.getByText("Anna Schmidt")).toBeDefined();
  });

  it("shows confidence percentage", () => {
    render(
      <ExtractionItemCard
        item={makeItem({ confidence: 0.92 })}
        isSelected={true}
        onToggle={vi.fn()}
      />,
    );

    // The i18n mock returns "kb.extractionConfidenceLabel" with {score} replaced by 92
    expect(screen.getByText("kb.extractionConfidenceLabel")).toBeDefined();
  });

  it("shows source text when expanded", () => {
    render(
      <ExtractionItemCard
        item={makeItem({ source_text: "She walked through the old archive." })}
        isSelected={true}
        onToggle={vi.fn()}
      />,
    );

    // Source text is collapsed by default — click to expand
    fireEvent.click(screen.getByText("kb.extractionViewSource"));

    // After expanding, the source text should be visible
    expect(screen.getByText("kb.extractionSourceText")).toBeDefined();
  });

  it("calls onToggle when checkbox area is clicked", () => {
    const onToggle = vi.fn();

    render(<ExtractionItemCard item={makeItem()} isSelected={false} onToggle={onToggle} />);

    // The header button triggers onToggle
    const headerButton = screen.getByRole("button", { name: /Anna Schmidt/ });
    fireEvent.click(headerButton);

    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("conflict items show warning icon (AlertTriangle)", () => {
    const { container } = render(
      <ExtractionItemCard
        item={makeItem({
          item_type: "conflict",
          conflict_description: "Duplicate name detected",
        })}
        isSelected={true}
        onToggle={vi.fn()}
      />,
    );

    // AlertTriangle SVG is rendered inside the badge for conflict items
    const svgIcons = container.querySelectorAll("svg");
    expect(svgIcons.length).toBeGreaterThanOrEqual(1);

    // Conflict description should be rendered
    expect(screen.getByText("kb.extractionConflictDescription")).toBeDefined();
  });

  it("relationship items show formatted name with related entity", () => {
    render(
      <ExtractionItemCard
        item={makeItem({
          item_type: "relationship",
          name: "Anna Schmidt",
          related_entity_name: "The Old Archive",
          relationship_type: "frequents",
        })}
        isSelected={true}
        onToggle={vi.fn()}
      />,
    );

    // The i18n mock returns "kb.extractionRelationshipFormat" with params interpolated
    // {name} → "Anna Schmidt", {related} → "The Old Archive"
    expect(screen.getByText("kb.extractionRelationshipFormat")).toBeDefined();
  });

  it("shows entity type label when present", () => {
    render(
      <ExtractionItemCard
        item={makeItem({ entity_type: "character" })}
        isSelected={true}
        onToggle={vi.fn()}
      />,
    );

    expect(screen.getByText("character")).toBeDefined();
  });

  it("shows proposed content section when present", () => {
    render(
      <ExtractionItemCard
        item={makeItem({ proposed_content: { role: "Protagonist", age: "28" } })}
        isSelected={true}
        onToggle={vi.fn()}
      />,
    );

    expect(screen.getByText("kb.extractionProposedContent")).toBeDefined();
  });

  it("applies selected styling when isSelected is true", () => {
    const { container } = render(
      <ExtractionItemCard item={makeItem()} isSelected={true} onToggle={vi.fn()} />,
    );

    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain("border-primary");
  });

  it("applies unselected styling when isSelected is false", () => {
    const { container } = render(
      <ExtractionItemCard item={makeItem()} isSelected={false} onToggle={vi.fn()} />,
    );

    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain("border-border");
  });
});
