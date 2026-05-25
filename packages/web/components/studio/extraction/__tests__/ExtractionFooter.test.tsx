/**
 * ExtractionFooter tests — Action buttons for the extraction panel.
 *
 * Tests:
 * 1. Shows selected count summary
 * 2. Apply button shows count
 * 3. Apply button disabled when 0 selected
 * 4. Cancel button calls onCancel
 * 5. Apply button calls onApply
 * 6. Apply button disabled when isApplying is true
 * 7. Shows applying state with spinner
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExtractionFooter } from "@/components/studio/extraction/ExtractionFooter";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ExtractionFooter", () => {
  it("shows selected count summary", () => {
    render(
      <ExtractionFooter
        selectedCount={3}
        totalCount={5}
        isApplying={false}
        onCancel={vi.fn()}
        onApply={vi.fn()}
      />,
    );

    // The i18n mock returns "kb.extractionSelectedSummary" with {count} and {total} interpolated
    expect(screen.getByText("kb.extractionSelectedSummary")).toBeDefined();
  });

  it("Apply button shows count of selected items", () => {
    render(
      <ExtractionFooter
        selectedCount={3}
        totalCount={5}
        isApplying={false}
        onCancel={vi.fn()}
        onApply={vi.fn()}
      />,
    );

    // The i18n mock returns "kb.extractionApply" with {count} replaced by 3
    expect(screen.getByText("kb.extractionApply")).toBeDefined();
  });

  it("Apply button is disabled when 0 selected", () => {
    render(
      <ExtractionFooter
        selectedCount={0}
        totalCount={5}
        isApplying={false}
        onCancel={vi.fn()}
        onApply={vi.fn()}
      />,
    );

    const applyButton = screen.getByText("kb.extractionApply").closest("button");
    expect(applyButton?.disabled).toBe(true);
  });

  it("Cancel button calls onCancel", () => {
    const onCancel = vi.fn();

    render(
      <ExtractionFooter
        selectedCount={3}
        totalCount={5}
        isApplying={false}
        onCancel={onCancel}
        onApply={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByText("kb.extractionCancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("Apply button calls onApply when clicked", () => {
    const onApply = vi.fn();

    render(
      <ExtractionFooter
        selectedCount={3}
        totalCount={5}
        isApplying={false}
        onCancel={vi.fn()}
        onApply={onApply}
      />,
    );

    fireEvent.click(screen.getByText("kb.extractionApply"));
    expect(onApply).toHaveBeenCalledTimes(1);
  });

  it("Apply button is disabled when isApplying is true", () => {
    render(
      <ExtractionFooter
        selectedCount={3}
        totalCount={5}
        isApplying={true}
        onCancel={vi.fn()}
        onApply={vi.fn()}
      />,
    );

    // When applying, the button shows "kb.extractionApplying" text
    const applyButton = screen.getByText("kb.extractionApplying").closest("button");
    expect(applyButton?.disabled).toBe(true);
  });

  it("shows applying state text when isApplying is true", () => {
    render(
      <ExtractionFooter
        selectedCount={3}
        totalCount={5}
        isApplying={true}
        onCancel={vi.fn()}
        onApply={vi.fn()}
      />,
    );

    // The applying text replaces the apply text
    expect(screen.getByText("kb.extractionApplying")).toBeDefined();
    expect(screen.queryByText("kb.extractionApply")).toBeNull();
  });

  it("Apply button is enabled when items are selected and not applying", () => {
    render(
      <ExtractionFooter
        selectedCount={2}
        totalCount={5}
        isApplying={false}
        onCancel={vi.fn()}
        onApply={vi.fn()}
      />,
    );

    const applyButton = screen.getByText("kb.extractionApply").closest("button");
    expect(applyButton?.disabled).toBe(false);
  });
});
