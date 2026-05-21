/**
 * Unit tests for StructureChangeDialog AI display features.
 *
 * Verifies that the AI confidence badge appears when ai_confidence > 0,
 * and is hidden when ai_confidence = 0.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StructureChangeDialog } from "@/components/studio/planning/StructureChangeDialog";

// Mock the TanStack Query hooks used by the dialog
vi.mock("@/lib/hooks/usePlanning", () => ({
  usePreviewRemap: vi.fn(),
  useConfirmRemap: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
}));

import { usePreviewRemap } from "@/lib/hooks/usePlanning";

const mockUsePreviewRemap = usePreviewRemap as ReturnType<typeof vi.fn>;

// next-intl and next/navigation are mocked globally in setupTests.ts

describe("StructureChangeDialog — AI display", () => {
  const defaultProps = {
    open: true,
    novelId: "novel-1",
    newStructure: "five_act",
    currentStructure: "three_act",
    onClose: vi.fn(),
    onCancel: vi.fn(),
  };

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const defaultPreview = {
    new_structure: "five_act",
    remapped: [],
    confirmed: false,
  };

  it("shows AI confidence badge when ai_confidence > 0", () => {
    mockUsePreviewRemap.mockReturnValue({
      data: {
        ...defaultPreview,
        ai_confidence: 0.85,
        remapped: [
          {
            chapter_id: "ch-1",
            chapter_title: "Chapter 1",
            old_stage: "act-1",
            new_stage: "exposition",
          },
        ],
      },
      isPending: false,
      isError: false,
      mutate: vi.fn(),
    });

    render(<StructureChangeDialog {...defaultProps} />);

    // The aiConfidence badge should be rendered (i18n mock returns the key as-is)
    expect(screen.getByText("storyboard.remap.aiConfidence")).toBeInTheDocument();
  });

  it("hides AI confidence badge when ai_confidence is 0 or not set", () => {
    mockUsePreviewRemap.mockReturnValue({
      data: {
        ...defaultPreview,
        ai_confidence: 0,
        remapped: [
          {
            chapter_id: "ch-1",
            chapter_title: "Chapter 1",
            old_stage: "act-1",
            new_stage: "exposition",
          },
        ],
      },
      isPending: false,
      isError: false,
      mutate: vi.fn(),
    });

    render(<StructureChangeDialog {...defaultProps} />);

    // The AI confidence badge should not be present
    expect(screen.queryByText(/AI/)).not.toBeInTheDocument();
  });

  it("hides AI confidence badge when ai_confidence is undefined", () => {
    mockUsePreviewRemap.mockReturnValue({
      data: defaultPreview,
      isPending: false,
      isError: false,
      mutate: vi.fn(),
    });

    render(<StructureChangeDialog {...defaultProps} />);

    // The AI confidence badge should not be present
    expect(screen.queryByText(/AI/)).not.toBeInTheDocument();
  });

  it("shows ✨ AI badge on rows where ai_suggested_stage differs from new_stage", () => {
    mockUsePreviewRemap.mockReturnValue({
      data: {
        ...defaultPreview,
        ai_confidence: 0.92,
        remapped: [
          {
            chapter_id: "ch-1",
            chapter_title: "Chapter 1",
            old_stage: "act-1",
            new_stage: "exposition",
            ai_suggested_stage: "rising-action",
          },
        ],
      },
      isPending: false,
      isError: false,
      mutate: vi.fn(),
    });

    render(<StructureChangeDialog {...defaultProps} />);

    // The AI suggested badge should be visible
    expect(screen.getByText("storyboard.remap.aiSuggested")).toBeInTheDocument();
  });

  it("hides AI badge when ai_suggested_stage matches new_stage", () => {
    mockUsePreviewRemap.mockReturnValue({
      data: {
        ...defaultPreview,
        ai_confidence: 0.92,
        remapped: [
          {
            chapter_id: "ch-1",
            chapter_title: "Chapter 1",
            old_stage: "act-1",
            new_stage: "exposition",
            ai_suggested_stage: "exposition",
          },
        ],
      },
      isPending: false,
      isError: false,
      mutate: vi.fn(),
    });

    render(<StructureChangeDialog {...defaultProps} />);

    // The AI suggested badge should NOT be visible (suggestion matches assigned)
    expect(screen.queryByText("storyboard.remap.aiSuggested")).not.toBeInTheDocument();
  });
});
