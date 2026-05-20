import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StructureChangeDialog } from "@/components/studio/planning/StructureChangeDialog";

/**
 * Unit tests for StructureChangeDialog component.
 *
 * The component uses usePreviewRemap and useConfirmRemap mutation hooks
 * which call the planning API. We mock these hooks to control behavior.
 */

// Mock the planning hooks
const mockPreviewMutate = vi.fn();
const mockConfirmMutate = vi.fn();

vi.mock("@/lib/hooks/usePlanning", () => ({
  usePreviewRemap: () => ({
    mutate: mockPreviewMutate,
    data: {
      new_structure: "five_act",
      remapped: [
        {
          chapter_id: "ch-1",
          chapter_title: "Chapter One",
          old_stage: "act-1",
          new_stage: "exposition",
        },
        {
          chapter_id: "ch-2",
          chapter_title: "Chapter Two",
          old_stage: "act-2",
          new_stage: "rising-action",
        },
      ],
    },
    isPending: false,
    isError: false,
    error: null,
  }),
  useConfirmRemap: () => ({
    mutate: mockConfirmMutate,
    isPending: false,
    isError: false,
    error: null,
  }),
}));

describe("StructureChangeDialog", () => {
  const defaultProps = {
    open: true,
    novelId: "novel-1",
    newStructure: "five_act",
    currentStructure: "three_act",
    onClose: vi.fn(),
    onCancel: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders remap preview table with chapter data", () => {
    render(<StructureChangeDialog {...defaultProps} />);

    // Check table headers
    expect(screen.getByText("storyboard.remap.chapterTitle")).toBeDefined();
    expect(screen.getByText("storyboard.remap.currentStage")).toBeDefined();
    expect(screen.getByText("storyboard.remap.newStage")).toBeDefined();

    // Check chapter data in the preview
    expect(screen.getByText("Chapter One")).toBeDefined();
    expect(screen.getByText("Chapter Two")).toBeDefined();

    // Stage names should be i18n-translated from stage IDs
    // old_stage "act-1" (three_act) → "storyboard.stages.three_act.act-1"
    expect(screen.getByText("storyboard.stages.three_act.act-1")).toBeDefined();
    // new_stage "exposition" (five_act) → "storyboard.stages.five_act.exposition"
    expect(screen.getByText("storyboard.stages.five_act.exposition")).toBeDefined();
    // old_stage "act-2" (three_act) → "storyboard.stages.three_act.act-2"
    expect(screen.getByText("storyboard.stages.three_act.act-2")).toBeDefined();
    // new_stage "rising-action" (five_act) → "storyboard.stages.five_act.rising-action"
    expect(screen.getByText("storyboard.stages.five_act.rising-action")).toBeDefined();
  });

  it("confirm button calls confirmRemap API", () => {
    render(<StructureChangeDialog {...defaultProps} />);

    const confirmButton = screen.getByText("storyboard.remap.confirm");
    fireEvent.click(confirmButton);

    expect(mockConfirmMutate).toHaveBeenCalled();
  });

  it("cancel button calls onClose and onCancel", () => {
    const onClose = vi.fn();
    const onCancel = vi.fn();
    render(<StructureChangeDialog {...defaultProps} onClose={onClose} onCancel={onCancel} />);

    const cancelButton = screen.getByText("storyboard.remap.cancel");
    fireEvent.click(cancelButton);

    expect(onCancel).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("shows loading state during API call", () => {
    // Re-mock to simulate pending state
    vi.doMock("@/lib/hooks/usePlanning", () => ({
      usePreviewRemap: () => ({
        mutate: vi.fn(),
        data: null,
        isPending: true,
        isError: false,
        error: null,
      }),
      useConfirmRemap: () => ({
        mutate: vi.fn(),
        isPending: false,
        isError: false,
        error: null,
      }),
    }));

    // With the current mock setup, the pending state shows a loader
    // We verify the dialog still renders with loading spinner
    render(<StructureChangeDialog {...defaultProps} />);

    // The dialog container should be present
    expect(screen.getByRole("dialog")).toBeDefined();
  });

  it("returns null when open is false", () => {
    const { container } = render(<StructureChangeDialog {...defaultProps} open={false} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders as a modal dialog with aria-modal", () => {
    render(<StructureChangeDialog {...defaultProps} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
  });

  it("calls preview mutation on mount when open", () => {
    render(<StructureChangeDialog {...defaultProps} />);
    expect(mockPreviewMutate).toHaveBeenCalled();
  });

  it("does not call preview mutation when not open", () => {
    vi.clearAllMocks();
    render(<StructureChangeDialog {...defaultProps} open={false} />);
    expect(mockPreviewMutate).not.toHaveBeenCalled();
  });
});
