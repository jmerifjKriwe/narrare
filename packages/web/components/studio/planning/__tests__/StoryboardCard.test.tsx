import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StoryboardCard } from "@/components/studio/planning/StoryboardCard";
import type { ChapterInStoryboard } from "@/types";

/**
 * Unit tests for StoryboardCard component.
 *
 * The @dnd-kit useDraggable hook is mocked to avoid requiring a DndContext
 * wrapper in tests. The mock provides the essential props (ref, attributes,
 * listeners, isDragging) without real drag behavior.
 */

// Mock @dnd-kit/core to avoid needing DndContext wrapper
vi.mock("@dnd-kit/core", () => ({
  useDraggable: ({ id, data }: { id: string; data: Record<string, unknown> }) => ({
    attributes: { role: "button", tabIndex: 0, "aria-describedby": id },
    listeners: { onPointerDown: vi.fn() },
    setNodeRef: vi.fn(),
    isDragging: false,
    id,
    data,
  }),
}));

const baseChapter: ChapterInStoryboard = {
  chapter_id: "ch-1",
  title: "The Beginning",
  word_count: 2500,
  sync_status: "on_track",
  position: 0,
};

describe("StoryboardCard", () => {
  it("renders chapter title", () => {
    render(<StoryboardCard chapter={baseChapter} onNavigate={vi.fn()} />);
    expect(screen.getByText("The Beginning")).toBeDefined();
  });

  it("renders word count", () => {
    render(<StoryboardCard chapter={baseChapter} onNavigate={vi.fn()} />);
    // The mock returns the key with params interpolated: "editor.words" becomes "editor.words" (no translation)
    // Actually the mock replaces {count} => 2500, so it's "editor.words" with {count} replaced
    expect(screen.getByText("editor.words")).toBeDefined();
  });

  it("shows correct SyncStatusBadge based on chapter status", () => {
    render(<StoryboardCard chapter={baseChapter} onNavigate={vi.fn()} />);
    expect(screen.getByText("storyboard.status.on_track")).toBeDefined();
  });

  it("calls onNavigate when clicked (without drag)", () => {
    const onNavigate = vi.fn();
    render(<StoryboardCard chapter={baseChapter} onNavigate={onNavigate} />);

    // Click the inner button (aria-label from i18n mock)
    const button = screen.getByRole("button", { name: /openChapter/i });
    fireEvent.click(button);
    expect(onNavigate).toHaveBeenCalledWith("ch-1");
  });

  it("renders different status badges correctly", () => {
    const deviatedChapter: ChapterInStoryboard = {
      ...baseChapter,
      sync_status: "deviated",
    };
    render(<StoryboardCard chapter={deviatedChapter} onNavigate={vi.fn()} />);
    expect(screen.getByText("storyboard.status.deviated")).toBeDefined();
  });

  it("renders completed status badge", () => {
    const completedChapter: ChapterInStoryboard = {
      ...baseChapter,
      sync_status: "completed",
    };
    render(<StoryboardCard chapter={completedChapter} onNavigate={vi.fn()} />);
    expect(screen.getByText("storyboard.status.completed")).toBeDefined();
  });
});
