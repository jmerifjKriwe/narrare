/**
 * StoryboardStageColumn tests — stage column with chapter cards.
 *
 * Tests:
 * 1. Renders stage name as header
 * 2. Renders chapter cards
 * 3. Renders empty slot when no chapters
 * 4. Shows drop zone styling when isOver
 * 5. Calls onNavigate when chapter card clicked
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StoryboardStageColumn } from "@/components/studio/planning/StoryboardStageColumn";
import type { StoryboardStageResponse } from "@/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@dnd-kit/core", () => ({
  useDroppable: ({ id }: { id: string }) => ({
    isOver: false,
    setNodeRef: vi.fn(),
    id,
  }),
}));

vi.mock("@/components/studio/planning/StoryboardCard", () => ({
  StoryboardCard: ({
    chapter,
    onNavigate,
  }: {
    chapter: { chapter_id: string; title: string };
    onNavigate: (id: string) => void;
  }) => (
    <button type="button" onClick={() => onNavigate(chapter.chapter_id)}>
      {chapter.title}
    </button>
  ),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function createStage(overrides: Partial<StoryboardStageResponse> = {}): StoryboardStageResponse {
  return {
    stage_id: "act-1",
    stage_name: "Act 1",
    chapters: [
      {
        chapter_id: "ch-1",
        title: "The Beginning",
        word_count: 2500,
        sync_status: "on_track",
        position: 0,
      },
    ],
    ...overrides,
  };
}

const defaultProps = {
  stage: createStage(),
  onNavigate: vi.fn(),
  structureType: "three_act",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("StoryboardStageColumn", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders stage name as header", () => {
    render(<StoryboardStageColumn {...defaultProps} />);

    // The i18n mock returns the key, not the actual name
    // getStageName() tries t("storyboard.stages.three_act.act-1") which returns the key
    expect(screen.getByText("storyboard.stages.three_act.act-1")).toBeDefined();
  });

  it("renders chapter cards", () => {
    render(<StoryboardStageColumn {...defaultProps} />);

    expect(screen.getByText("The Beginning")).toBeDefined();
  });

  it("renders empty slot when no chapters", () => {
    render(<StoryboardStageColumn {...defaultProps} stage={createStage({ chapters: [] })} />);

    expect(screen.getByText("storyboard.emptySlot")).toBeDefined();
  });

  it("calls onNavigate when chapter card clicked", () => {
    const onNavigate = vi.fn();
    render(<StoryboardStageColumn {...defaultProps} onNavigate={onNavigate} />);

    fireEvent.click(screen.getByText("The Beginning"));
    expect(onNavigate).toHaveBeenCalledWith("ch-1");
  });

  it("renders multiple chapters", () => {
    const stage = createStage({
      chapters: [
        {
          chapter_id: "ch-1",
          title: "Chapter One",
          word_count: 1000,
          sync_status: "on_track",
          position: 0,
        },
        {
          chapter_id: "ch-2",
          title: "Chapter Two",
          word_count: 2000,
          sync_status: "on_track",
          position: 1,
        },
      ],
    });

    render(<StoryboardStageColumn {...defaultProps} stage={stage} />);

    expect(screen.getByText("Chapter One")).toBeDefined();
    expect(screen.getByText("Chapter Two")).toBeDefined();
  });

  it("renders with column styling", () => {
    const { container } = render(<StoryboardStageColumn {...defaultProps} />);

    const column = container.firstChild as HTMLElement;
    expect(column.className).toContain("rounded-lg");
  });
});
