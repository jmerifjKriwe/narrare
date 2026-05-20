import type { DragEndEvent } from "@dnd-kit/core";
import { act, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StoryboardPanel } from "@/components/studio/planning/StoryboardPanel";
import { useEditorStore } from "@/lib/stores/editorStore";

/**
 * Unit tests for drag-and-drop behavior in the Storyboard.
 *
 * Since @dnd-kit requires a complex setup for real DnD events, we test
 * the drag end handler by capturing the onDragEnd callback from the
 * DndContext mock and simulating drag events directly.
 *
 * We verify:
 * 1. A drag that moves a chapter to a different stage triggers updateOutline
 * 2. A drag canceled (null over) does NOT trigger updateOutline
 */

const mockMutate = vi.fn();

// Polyfill ResizeObserver for jsdom
class MockResizeObserver {
  constructor(_callback: ResizeObserverCallback) {}
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal("ResizeObserver", MockResizeObserver);

// Mock @dnd-kit/core — DndContext captures onDragEnd for testing
vi.mock("@dnd-kit/core", () => ({
  DndContext: ({
    children,
    onDragEnd,
  }: {
    children: React.ReactNode;
    onDragEnd: (event: DragEndEvent) => void;
    onDragStart?: (event: unknown) => void;
    onDragCancel?: () => void;
    sensors: unknown[];
  }) => {
    // Expose onDragEnd globally for test access
    (globalThis as unknown as Record<string, (event: DragEndEvent) => void>).__testOnDragEnd =
      onDragEnd;
    return <>{children}</>;
  },
  DragOverlay: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  PointerSensor: class {},
  useSensor: () => ({}),
  useSensors: () => [],
  useDraggable: ({ id, data }: { id: string; data: Record<string, unknown> }) => ({
    attributes: { role: "button", tabIndex: 0, "aria-describedby": id },
    listeners: {},
    setNodeRef: vi.fn(),
    isDragging: false,
    id,
    data,
  }),
  useDroppable: ({ id, data }: { id: string; data: Record<string, unknown> }) => ({
    isOver: false,
    setNodeRef: vi.fn(),
    id,
    data,
  }),
}));

const mockStoryboard = {
  structure_type: "three_act",
  stages: [
    {
      stage_id: "act-1",
      stage_name: "Act 1",
      chapters: [
        {
          chapter_id: "ch-1",
          title: "Chapter One",
          word_count: 2500,
          sync_status: "on_track" as const,
          position: 0,
        },
      ],
    },
    {
      stage_id: "act-2",
      stage_name: "Act 2",
      chapters: [],
    },
    {
      stage_id: "act-3",
      stage_name: "Act 3",
      chapters: [],
    },
  ],
};

vi.mock("@/lib/hooks/usePlanning", () => ({
  useStoryboard: () => ({
    data: mockStoryboard,
    isLoading: false,
  }),
  useUpdateOutline: () => ({
    mutate: mockMutate,
    isPending: false,
  }),
}));

describe("Storyboard DnD", () => {
  beforeEach(() => {
    mockMutate.mockClear();
    useEditorStore.setState({ storyboardOpen: true });
    // Clear the captured handler
    delete (globalThis as unknown as Record<string, unknown>).__testOnDragEnd;
  });

  it("dragging a card to a different stage triggers updateOutline API call", async () => {
    await act(async () => {
      render(<StoryboardPanel novelId="novel-1" />);
    });

    const onDragEnd = (globalThis as unknown as Record<string, (event: DragEndEvent) => void>)
      .__testOnDragEnd;

    expect(onDragEnd).toBeDefined();

    // Simulate a drag end event: chapter ch-1 dropped on act-2
    onDragEnd({
      active: {
        id: "chapter-ch-1",
        data: { current: { chapterId: "ch-1" } },
      } as unknown as Parameters<typeof onDragEnd>[0]["active"],
      over: {
        id: "stage-act-2",
        data: { current: { stageId: "act-2" } },
      } as unknown as Parameters<typeof onDragEnd>[0]["over"],
    } as DragEndEvent);

    expect(mockMutate).toHaveBeenCalledWith({
      chapterId: "ch-1",
      data: { stage_assignment: "act-2" },
    });
  });

  it("canceling a drag does not trigger updateOutline", async () => {
    await act(async () => {
      render(<StoryboardPanel novelId="novel-1" />);
    });

    const onDragEnd = (globalThis as unknown as Record<string, (event: DragEndEvent) => void>)
      .__testOnDragEnd;

    // Simulate drag cancel (over is null)
    onDragEnd({
      active: {
        id: "chapter-ch-1",
        data: { current: { chapterId: "ch-1" } },
      } as unknown as Parameters<typeof onDragEnd>[0]["active"],
      over: null,
    } as unknown as DragEndEvent);

    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("does not trigger API when active data is missing", async () => {
    await act(async () => {
      render(<StoryboardPanel novelId="novel-1" />);
    });

    const onDragEnd = (globalThis as unknown as Record<string, (event: DragEndEvent) => void>)
      .__testOnDragEnd;

    // Simulate drag with no data
    onDragEnd({
      active: {
        id: "chapter-ch-1",
        data: { current: null },
      } as unknown as Parameters<typeof onDragEnd>[0]["active"],
      over: {
        id: "stage-act-2",
        data: { current: { stageId: "act-2" } },
      } as unknown as Parameters<typeof onDragEnd>[0]["over"],
    } as DragEndEvent);

    // chapterId will be "" (empty string from null replacement), which is falsy
    expect(mockMutate).not.toHaveBeenCalled();
  });
});
