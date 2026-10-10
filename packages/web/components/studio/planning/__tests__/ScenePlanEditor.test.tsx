/**
 * ScenePlanEditor tests — chapter scene-plan aggregate editing.
 *
 * Tests:
 * 1. Renders the chapter's scenes in order (SceneCards)
 * 2. Empty aggregate shows the empty state; add-scene PUTs a new UUID scene
 * 3. No chapter selected shows the noChapter state
 * 4. Move down reorders and PUTs the aggregate in the new order (renumbered)
 * 5. Draft with AI inserts proposals as new scenes (UUID ids, appended positions)
 * 6. Draft with AI unavailable shows aiUnavailable and does not save
 * 7. Save button PUTs the current local scenes
 * 8. Remove drops the scene and PUTs the remaining aggregate
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScenePlanEditor } from "@/components/studio/planning/ScenePlanEditor";
import { server } from "@/mocks/server";
import type { ScenePlan, ScenePlanAggregate } from "@/types/planning";

// ---------------------------------------------------------------------------
// Fixtures
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
    makeScene({ id: "scene-b", position: 2, title: "Twist", beats: ["Reveal"] }),
  ],
  version_updated_at: "2026-01-01T00:00:00Z",
};

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;

// ---------------------------------------------------------------------------
// Harness — captures PUT bodies via MSW
// ---------------------------------------------------------------------------

interface Harness {
  putBodies: Array<{ scenes: Array<Record<string, unknown>> }>;
  render: (chapterId?: string | null) => void;
}

function setup(): Harness {
  const putBodies: Harness["putBodies"] = [];
  server.use(
    http.get("*/api/v1/planning/scenes/:novelId/:chapterId", async () => {
      return HttpResponse.json(aggregate);
    }),
    http.put("*/api/v1/planning/scenes/:novelId/:chapterId", async ({ request }) => {
      const body = (await request.json()) as Harness["putBodies"][number];
      putBodies.push(body);
      return HttpResponse.json({ ...aggregate, scenes: body.scenes });
    }),
    http.post("*/api/v1/planning/scenes/:novelId/:chapterId/draft", async () => {
      return HttpResponse.json({
        proposals: [
          {
            title: "Drafted A",
            pov_character_ref: null,
            location_ref: null,
            present_characters: [],
            purpose: "Draft purpose",
            conflict: "",
            resolution: "",
            beats: [],
          },
        ],
        ai_unavailable: false,
      });
    }),
  );

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return {
    putBodies,
    render(chapterId: string | null = "chapter-1") {
      render(
        <QueryClientProvider client={queryClient}>
          <ScenePlanEditor novelId="novel-1" chapterId={chapterId} />
        </QueryClientProvider>,
      );
    },
  };
}

describe("ScenePlanEditor", () => {
  let harness: Harness;

  beforeEach(() => {
    vi.clearAllMocks();
    harness = setup();
  });

  it("renders the chapter's scenes in order", async () => {
    harness.render();

    await waitFor(() => {
      expect(screen.getByText("Opening")).toBeDefined();
    });
    expect(screen.getByText("Twist")).toBeDefined();
    expect(screen.getByText("#1")).toBeDefined();
    expect(screen.getByText("#2")).toBeDefined();
  });

  it("shows the empty state and adds a scene with a UUID id via PUT", async () => {
    server.use(
      http.get("*/api/v1/planning/scenes/:novelId/:chapterId", async () => {
        return HttpResponse.json({ ...aggregate, scenes: [] });
      }),
    );
    harness.render();

    await waitFor(() => {
      expect(screen.getByText("empty")).toBeDefined();
    });
    fireEvent.click(screen.getByText("addScene"));

    await waitFor(() => {
      expect(harness.putBodies).toHaveLength(1);
    });
    const saved = harness.putBodies[0]!.scenes;
    expect(saved).toHaveLength(1);
    expect(UUID_RE.test(String(saved[0]!.id))).toBe(true);
    expect(saved[0]).toMatchObject({ position: 1, status: "planned" });
  });

  it("shows the noChapter state when no chapter is selected", () => {
    harness.render(null);

    expect(screen.getByText("noChapter")).toBeDefined();
  });

  it("reorders on moveDown and PUTs the renumbered aggregate", async () => {
    harness.render();

    await waitFor(() => {
      expect(screen.getByText("Opening")).toBeDefined();
    });
    fireEvent.click(screen.getAllByLabelText("moveDown")[0]);

    await waitFor(() => {
      expect(harness.putBodies).toHaveLength(1);
    });
    const saved = harness.putBodies[0]!.scenes;
    expect(saved.map((s) => s.title)).toEqual(["Twist", "Opening"]);
    expect(saved.map((s) => s.position)).toEqual([1, 2]);
  });

  it("inserts draft proposals as new scenes with UUID ids and appended positions", async () => {
    harness.render();

    await waitFor(() => {
      expect(screen.getByText("Opening")).toBeDefined();
    });
    fireEvent.click(screen.getByText("draftWithAi"));

    await waitFor(() => {
      expect(harness.putBodies).toHaveLength(1);
    });
    const saved = harness.putBodies[0]!.scenes;
    expect(saved).toHaveLength(3);
    const inserted = saved[2]!;
    expect(UUID_RE.test(String(inserted.id))).toBe(true);
    expect(inserted).toMatchObject({ title: "Drafted A", position: 3, status: "planned" });
  });

  it("shows aiUnavailable and does not save when the draft generator is unavailable", async () => {
    server.use(
      http.post("*/api/v1/planning/scenes/:novelId/:chapterId/draft", async () => {
        return HttpResponse.json({ proposals: [], ai_unavailable: true });
      }),
    );
    harness.render();

    await waitFor(() => {
      expect(screen.getByText("Opening")).toBeDefined();
    });
    fireEvent.click(screen.getByText("draftWithAi"));

    await waitFor(() => {
      expect(screen.getByText("aiUnavailable")).toBeDefined();
    });
    expect(harness.putBodies).toHaveLength(0);
  });

  it("shows the graceful notice when a successful draft returns zero proposals", async () => {
    server.use(
      http.post("*/api/v1/planning/scenes/:novelId/:chapterId/draft", async () => {
        return HttpResponse.json({ proposals: [], ai_unavailable: false });
      }),
    );
    harness.render();

    await waitFor(() => {
      expect(screen.getByText("Opening")).toBeDefined();
    });
    fireEvent.click(screen.getByText("draftWithAi"));

    await waitFor(() => {
      expect(screen.getByText("aiUnavailable")).toBeDefined();
    });
    expect(harness.putBodies).toHaveLength(0);
  });

  it("saves the current local scenes via the save button", async () => {
    harness.render();

    await waitFor(() => {
      expect(screen.getByText("Opening")).toBeDefined();
    });
    fireEvent.click(screen.getByText("save"));

    await waitFor(() => {
      expect(harness.putBodies).toHaveLength(1);
    });
    expect(harness.putBodies[0]!.scenes.map((s) => s.id)).toEqual(["scene-a", "scene-b"]);
  });

  it("removes a scene and PUTs the renumbered remainder", async () => {
    harness.render();

    await waitFor(() => {
      expect(screen.getByText("Opening")).toBeDefined();
    });
    fireEvent.click(screen.getAllByLabelText("remove")[0]);

    await waitFor(() => {
      expect(harness.putBodies).toHaveLength(1);
    });
    const saved = harness.putBodies[0]!.scenes;
    expect(saved.map((s) => s.title)).toEqual(["Twist"]);
    expect(saved[0]).toMatchObject({ position: 1 });
  });
});
