/**
 * ExtractionContent tests — phase-based content renderer.
 *
 * Tests:
 * 1. Renders ExtractionLoading for loading phase
 * 2. Renders ExtractionLoading for applying phase
 * 3. Renders ExtractionReview for review phase
 * 4. Renders ExtractionDone for done phase
 * 5. Renders ExtractionError for error phase with message
 * 6. Returns null for unknown state
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExtractionContent } from "@/components/studio/extraction/ExtractionContent";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/components/studio/extraction/ExtractionLoading", () => ({
  ExtractionLoading: () => <div data-testid="extraction-loading">Loading</div>,
}));

vi.mock("@/components/studio/extraction/ExtractionReview", () => ({
  ExtractionReview: ({ items }: { items: { name: string }[] }) => (
    <div data-testid="extraction-review">Review: {items.map((i) => i.name).join(", ")}</div>
  ),
}));

vi.mock("@/components/studio/extraction/ExtractionDone", () => ({
  ExtractionDone: () => <div data-testid="extraction-done">Done</div>,
}));

vi.mock("@/components/studio/extraction/ExtractionError", () => ({
  ExtractionError: ({ message }: { message: string }) => (
    <div data-testid="extraction-error">Error: {message}</div>
  ),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultItems = [
  {
    item_type: "new_entity" as const,
    entity_type: "character",
    name: "Anna",
    confidence: 0.85,
    source_text: "Anna walked into the room.",
    proposed_content: null,
    target_entity_id: null,
    conflict_description: null,
    relationship_type: null,
    related_entity_name: null,
  },
];
const defaultSelected = new Set<number>();
const noop = vi.fn();

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ExtractionContent", () => {
  it("renders ExtractionLoading for loading phase", () => {
    render(
      <ExtractionContent
        phase="loading"
        items={defaultItems}
        selectedIndices={defaultSelected}
        analysisNotes=""
        errorMsg={null}
        onToggleItem={noop}
        onSelectAll={noop}
        onSelectNone={noop}
        onRetry={noop}
      />,
    );

    expect(screen.getByTestId("extraction-loading")).toBeDefined();
  });

  it("renders ExtractionLoading for applying phase", () => {
    render(
      <ExtractionContent
        phase="applying"
        items={defaultItems}
        selectedIndices={defaultSelected}
        analysisNotes=""
        errorMsg={null}
        onToggleItem={noop}
        onSelectAll={noop}
        onSelectNone={noop}
        onRetry={noop}
      />,
    );

    expect(screen.getByTestId("extraction-loading")).toBeDefined();
  });

  it("renders ExtractionReview for review phase", () => {
    render(
      <ExtractionContent
        phase="review"
        items={defaultItems}
        selectedIndices={defaultSelected}
        analysisNotes="Some notes"
        errorMsg={null}
        onToggleItem={noop}
        onSelectAll={noop}
        onSelectNone={noop}
        onRetry={noop}
      />,
    );

    expect(screen.getByTestId("extraction-review")).toBeDefined();
  });

  it("renders ExtractionDone for done phase", () => {
    render(
      <ExtractionContent
        phase="done"
        items={[]}
        selectedIndices={defaultSelected}
        analysisNotes=""
        errorMsg={null}
        onToggleItem={noop}
        onSelectAll={noop}
        onSelectNone={noop}
        onRetry={noop}
      />,
    );

    expect(screen.getByTestId("extraction-done")).toBeDefined();
  });

  it("renders ExtractionError for error phase with message", () => {
    render(
      <ExtractionContent
        phase="error"
        items={[]}
        selectedIndices={defaultSelected}
        analysisNotes=""
        errorMsg="Something went wrong"
        onToggleItem={noop}
        onSelectAll={noop}
        onSelectNone={noop}
        onRetry={noop}
      />,
    );

    expect(screen.getByTestId("extraction-error")).toBeDefined();
    expect(screen.getByText("Error: Something went wrong")).toBeDefined();
  });

  it("returns null for error phase without message", () => {
    const { container } = render(
      <ExtractionContent
        phase="error"
        items={[]}
        selectedIndices={defaultSelected}
        analysisNotes=""
        errorMsg={null}
        onToggleItem={noop}
        onSelectAll={noop}
        onSelectNone={noop}
        onRetry={noop}
      />,
    );

    // Error phase requires errorMsg to render
    expect(container.innerHTML).toBe("");
  });
});
