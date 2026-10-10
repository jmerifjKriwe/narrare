/**
 * SceneCard tests — compact scene display + expand-to-edit.
 *
 * Tests:
 * 1. Renders title, position, purpose/beats preview (collapsed)
 * 2. Status chip colour maps per status (planned/in_progress/complete)
 * 3. Move up / move down / remove fire callbacks; disabled at boundaries
 * 4. Expand renders the SceneForm; collapse hides it
 * 5. Edits from the expanded form emit onEdit with the patched scene
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SceneCard } from "@/components/studio/planning/SceneCard";
import type { ScenePlan } from "@/types/planning";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const scene: ScenePlan = {
  id: "scene-1",
  position: 2,
  title: "The Meeting",
  pov_character_ref: null,
  location_ref: null,
  present_characters: [],
  purpose: "Introduce the rivalry",
  conflict: "",
  resolution: "",
  beats: ["Arrival", "Argument"],
  status: "planned",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

interface RenderOptions {
  index?: number;
  total?: number;
}

function renderCard({
  index = 1,
  total = 3,
  current = scene,
}: RenderOptions & { current?: ScenePlan } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  const onEdit = vi.fn();
  const onMoveUp = vi.fn();
  const onMoveDown = vi.fn();
  const onRemove = vi.fn();
  const { unmount } = render(
    <QueryClientProvider client={queryClient}>
      <SceneCard
        scene={current}
        index={index}
        total={total}
        novelId="novel-1"
        chapterId="chapter-1"
        onEdit={onEdit}
        onMoveUp={onMoveUp}
        onMoveDown={onMoveDown}
        onRemove={onRemove}
      />
    </QueryClientProvider>,
  );
  return { onEdit, onMoveUp, onMoveDown, onRemove, unmount };
}

describe("SceneCard", () => {
  it("renders title, position and compact purpose/beats preview", () => {
    renderCard();

    expect(screen.getByText("The Meeting")).toBeDefined();
    expect(screen.getByText("#2")).toBeDefined();
    expect(screen.getByText("Introduce the rivalry")).toBeDefined();
    expect(screen.getByText(/Arrival · Argument/u)).toBeDefined();
  });

  it.each([
    ["planned", "statusPlanned", "bg-blue-100"],
    ["in_progress", "statusInProgress", "bg-yellow-100"],
    ["complete", "statusComplete", "bg-emerald-100"],
  ] as const)("maps status %s to the %s chip colour", (status, labelKey, expectedClass) => {
    renderCard({ current: { ...scene, status } });

    const chip = screen.getByText(labelKey);
    expect(chip.className).toContain(expectedClass);
  });

  it("fires move/remove callbacks", () => {
    const { onMoveUp, onMoveDown, onRemove } = renderCard();

    fireEvent.click(screen.getByLabelText("moveUp"));
    expect(onMoveUp).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByLabelText("moveDown"));
    expect(onMoveDown).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByLabelText("remove"));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it("disables move-up on the first and move-down on the last card", () => {
    const first = renderCard({ index: 0, total: 3 });
    expect(screen.getByLabelText("moveUp")).toBeDisabled();
    expect(screen.getByLabelText("moveDown")).toBeEnabled();
    first.unmount();

    renderCard({ index: 2, total: 3 });
    expect(screen.getByLabelText("moveUp")).toBeEnabled();
    expect(screen.getByLabelText("moveDown")).toBeDisabled();
  });

  it("expands to the SceneForm and collapses back", () => {
    renderCard();

    expect(screen.queryByLabelText("sceneTitle")).toBeNull();

    fireEvent.click(screen.getByLabelText("expand"));
    expect(screen.getByLabelText("sceneTitle")).toHaveValue("The Meeting");

    fireEvent.click(screen.getByLabelText("collapse"));
    expect(screen.queryByLabelText("sceneTitle")).toBeNull();
  });

  it("emits onEdit with the patched scene from the expanded form", () => {
    const { onEdit } = renderCard();

    fireEvent.click(screen.getByLabelText("expand"));
    fireEvent.change(screen.getByLabelText("sceneTitle"), { target: { value: "Edited" } });

    expect(onEdit).toHaveBeenLastCalledWith(expect.objectContaining({ title: "Edited" }));
  });
});
