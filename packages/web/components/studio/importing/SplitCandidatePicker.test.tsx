/**
 * Tests for the split candidate picker (F1): selection toggling, apply
 * (sorted ordinals), the disabled-until-selected gate, cancel, and the
 * empty-candidates fallback.
 *
 * Uses the centralized setupTests.ts key-string i18n mock — assertions target
 * structure and behavior, not copy (rendered copy is pinned in
 * ImportPreviewPanel.test.tsx against the real catalog).
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SplitCandidatePicker } from "./SplitCandidatePicker";

const CANDIDATES = [
  // Deliberately unsorted: apply must emit ascending ordinals regardless.
  { ordinal: 1, heading: "Scene B", words_before: 6 },
  { ordinal: 0, heading: "Scene A", words_before: 2 },
];

function renderPicker(
  overrides: Partial<{
    candidates: typeof CANDIDATES;
    onApply: (ordinals: number[]) => void;
    onCancel: () => void;
  }> = {},
) {
  const onApply = overrides.onApply ?? vi.fn();
  const onCancel = overrides.onCancel ?? vi.fn();
  render(
    <SplitCandidatePicker
      candidates={overrides.candidates ?? CANDIDATES}
      onApply={onApply}
      onCancel={onCancel}
    />,
  );
  return { onApply, onCancel };
}

describe("SplitCandidatePicker", () => {
  it("emits the selected ordinals sorted ascending on apply", () => {
    const { onApply } = renderPicker();
    fireEvent.click(screen.getByLabelText("Scene B"));
    fireEvent.click(screen.getByLabelText("Scene A"));
    fireEvent.click(screen.getByTestId("apply-split-btn"));
    expect(onApply).toHaveBeenCalledWith([0, 1]);
  });

  it("keeps apply disabled until a candidate is selected", () => {
    renderPicker();
    const apply = screen.getByTestId("apply-split-btn") as HTMLButtonElement;
    expect(apply).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Scene A"));
    expect(apply).not.toBeDisabled();
  });

  it("cancel invokes onCancel without applying", () => {
    const { onApply, onCancel } = renderPicker();
    fireEvent.click(screen.getByLabelText("Scene A"));
    fireEvent.click(screen.getByRole("button", { name: "cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onApply).not.toHaveBeenCalled();
  });

  it("renders the empty-state fallback when the chapter has no candidates", () => {
    renderPicker({ candidates: [] });
    expect(screen.getByText("noSplitPoints")).toBeInTheDocument();
    expect(screen.queryByTestId("apply-split-btn")).not.toBeInTheDocument();
  });
});
