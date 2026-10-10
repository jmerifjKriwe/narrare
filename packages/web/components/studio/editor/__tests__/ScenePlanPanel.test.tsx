/**
 * ScenePlanPanel tests — compact editor scene-plan side panel (PLAN-001 §8.2).
 *
 * Tests:
 * 1. Renders the chapter's scenes (titles, purpose, status chips) via SceneCard
 * 2. Empty aggregate shows the empty state
 * 3. Missing chapter id shows the noChapter state
 * 4. Field edits stay LOCAL until Save; Save PUTs the edited aggregate
 * 5. Reorder persists immediately (renumbered PUT)
 * 6. "Open full planner" navigates to the Planning tab (scenes) and closes
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScenePlanPanel } from "@/components/studio/editor/ScenePlanPanel";
import { server } from "@/mocks/server";
import type { ScenePlan, ScenePlanAggregate } from "@/types/planning";

// ---------------------------------------------------------------------------
// Navigation mocks (URL-state push for the Planning tab)
// ---------------------------------------------------------------------------

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/novels/novel-1",
  useSearchParams: () => new URLSearchParams(),
}));

// ---------------------------------------------------------------------------
// Fixtures + harness
// ---------------------------------------------------------------------------

function makeScene(overrides: Partial<ScenePlan>): ScenePlan {
  return {
    id: `scene-${overrides.position}`,
    position: 1,
    title: "",
    pov_character_ref: null,
    location_ref: null,
    present_characters: [],
    purpose: "",
    conflict: "",
    resolution: "",
    beats: [],
    status: "planned",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const aggregate: ScenePlanAggregate = {
  chapter_id: "chapter-1",
  scenes: [
    makeScene({ id: "scene-a", position: 1, title: "Opening", purpose: "Set the stage" }),
    makeScene({ id: "scene-b", position: 2, title: "Twist", status: "in_progress" }),
  ],
  version_updated_at: "2026-01-01T00:00:00Z",
};

interface Harness {
  putBodies: Array<{ scenes: Array<Record<string, unknown>> }>;
  onClose: ReturnType<typeof vi.fn>;
  render: (chapterId?: string) => void;
}

function setup(): Harness {
  const putBodies: Harness["putBodies"] = [];
  const onClose = vi.fn();
  server.use(
    http.get("*/api/v1/planning/scenes/:novelId/:chapterId", async () => {
      return HttpResponse.json(aggregate);
    }),
    http.put("*/api/v1/planning/scenes/:novelId/:chapterId", async ({ request }) => {
      const body = (await request.json()) as Harness["putBodies"][number];
      putBodies.push(body);
      return HttpResponse.json({ ...aggregate, scenes: body.scenes });
    }),
  );

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return {
    putBodies,
    onClose,
    render(chapterId: string = "chapter-1") {
      render(
        <QueryClientProvider client={queryClient}>
          <ScenePlanPanel novelId="novel-1" chapterId={chapterId} onClose={onClose} />
        </QueryClientProvider>,
      );
    },
  };
}

describe("ScenePlanPanel", () => {
  let harness: Harness;

  beforeEach(() => {
    vi.clearAllMocks();
    harness = setup();
  });

  it("renders the chapter's scenes with title, purpose and status chip", async () => {
    harness.render();

    await waitFor(() => expect(screen.getByText("Opening")).toBeDefined());
    expect(screen.getByText("Set the stage")).toBeDefined();
    expect(screen.getByText("#1")).toBeDefined();
    // Status chips render through the shared SceneCard colour/label map.
    expect(screen.getByText("statusPlanned")).toBeDefined();
    expect(screen.getByText("statusInProgress")).toBeDefined();
  });

  it("shows the empty state for a chapter without scene plans", async () => {
    server.use(
      http.get("*/api/v1/planning/scenes/:novelId/:chapterId", async () => {
        return HttpResponse.json({ ...aggregate, scenes: [] });
      }),
    );
    harness.render();

    await waitFor(() => expect(screen.getByText("empty")).toBeDefined());
  });

  it("shows the noChapter state when no chapter is active", () => {
    harness.render("");

    expect(screen.getByText("noChapter")).toBeDefined();
  });

  it("keeps field edits local until Save PUTs the edited aggregate", async () => {
    harness.render();

    await waitFor(() => expect(screen.getByText("Opening")).toBeDefined());
    // Expand the first SceneCard → SceneForm appears.
    fireEvent.click(screen.getAllByLabelText("expand")[0]);
    const titleInput = await screen.findByLabelText("sceneTitle");
    fireEvent.change(titleInput, { target: { value: "Opening (edited)" } });

    // Local-only so far.
    expect(harness.putBodies).toHaveLength(0);

    fireEvent.click(screen.getByText("save"));
    await waitFor(() => expect(harness.putBodies).toHaveLength(1));

    const saved = harness.putBodies[0]!.scenes;
    expect(saved[0]).toMatchObject({ id: "scene-a", title: "Opening (edited)", position: 1 });
    expect(saved[1]).toMatchObject({ id: "scene-b" });
  });

  it("reorders immediately on moveDown with renumbered positions", async () => {
    harness.render();

    await waitFor(() => expect(screen.getByText("Opening")).toBeDefined());
    fireEvent.click(screen.getAllByLabelText("moveDown")[0]);

    await waitFor(() => expect(harness.putBodies).toHaveLength(1));
    const saved = harness.putBodies[0]!.scenes;
    expect(saved.map((s) => s.title)).toEqual(["Twist", "Opening"]);
    expect(saved.map((s) => s.position)).toEqual([1, 2]);
  });

  it("opens the full planner via planning URL state and closes the panel", async () => {
    harness.render();

    await waitFor(() => expect(screen.getByText("Opening")).toBeDefined());
    fireEvent.click(screen.getByText("openFullPlanner"));

    expect(mockPush).toHaveBeenCalledWith(
      "/novels/novel-1?planning=1&planningTab=scenes",
      expect.objectContaining({ scroll: false }),
    );
    expect(harness.onClose).toHaveBeenCalledOnce();
  });
});
