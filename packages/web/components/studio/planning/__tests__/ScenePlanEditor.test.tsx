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
 * 9. Draft POST body carries the sourced chapter context (PLAN-001 FU#1:
 *    structure_type, outline_notes, chapter_summary, neighbor_summaries)
 * 10. Context source failures degrade to an empty body — draft still works
 * 11. Empty/absent summaries omit their fields per-field (no invented values)
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScenePlanEditor } from "@/components/studio/planning/ScenePlanEditor";
import { server } from "@/mocks/server";
import type { Chapter } from "@/types";
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

function makeChapter(overrides: Partial<Chapter>): Chapter {
  return {
    id: "chapter-1",
    novel_id: "novel-1",
    volume_id: null,
    title: "Ballroom",
    content: "",
    summary: "",
    position: 2,
    word_count: 0,
    status: "draft",
    pov_character_id: "",
    timeline_position: "",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

/** Benign storyboard for context sourcing: chapter-1 sits between 0 and 2. */
function storyboardFixture() {
  return {
    structure_type: "three_act",
    stages: [
      {
        stage_id: "act_1",
        stage_name: "Act I",
        chapters: [
          {
            chapter_id: "chapter-0",
            title: "Cold Open",
            word_count: 100,
            sync_status: "empty",
            position: 1,
          },
          {
            chapter_id: "chapter-1",
            title: "Ballroom",
            word_count: 200,
            sync_status: "empty",
            position: 2,
          },
        ],
      },
      {
        stage_id: "act_2",
        stage_name: "Act II",
        chapters: [
          {
            chapter_id: "chapter-2",
            title: "Aftermath",
            word_count: 150,
            sync_status: "empty",
            position: 3,
          },
        ],
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// Harness — captures PUT bodies via MSW
// ---------------------------------------------------------------------------

interface Harness {
  putBodies: Array<{ scenes: Array<Record<string, unknown>> }>;
  /** Captured POST bodies of the AI-draft endpoint. */
  draftBodies: Array<Record<string, unknown>>;
  render: (chapterId?: string | null) => void;
}

function setup(): Harness {
  const putBodies: Harness["putBodies"] = [];
  const draftBodies: Harness["draftBodies"] = [];
  server.use(
    http.get("*/api/v1/planning/scenes/:novelId/:chapterId", async () => {
      return HttpResponse.json(aggregate);
    }),
    http.put("*/api/v1/planning/scenes/:novelId/:chapterId", async ({ request }) => {
      const body = (await request.json()) as Harness["putBodies"][number];
      putBodies.push(body);
      return HttpResponse.json({ ...aggregate, scenes: body.scenes });
    }),
    http.post("*/api/v1/planning/scenes/:novelId/:chapterId/draft", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      draftBodies.push(body);
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
    // Benign context sources (PLAN-001 FU#1): empty values so the legacy
    // tests keep seeing today's zero-context body shape.
    http.get("*/api/v1/planning/storyboard/:novelId", () =>
      HttpResponse.json({ structure_type: "three_act", stages: [] }),
    ),
    http.get("*/api/v1/planning/outlines/:novelId/:chapterId", () =>
      HttpResponse.json({
        id: "outline-1",
        chapter_id: "chapter-1",
        stage_assignment: "act_1",
        outline_notes: "",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      }),
    ),
    http.get("*/api/v1/novels/:novelId/chapters/:chapterId", ({ params }) =>
      HttpResponse.json(makeChapter({ id: String(params.chapterId) })),
    ),
  );

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return {
    putBodies,
    draftBodies,
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

  it("sends the sourced chapter context in the draft POST body", async () => {
    let contextGets = 0;
    const counted = () => {
      contextGets += 1;
    };
    server.use(
      http.get("*/api/v1/planning/storyboard/:novelId", () => {
        counted();
        return HttpResponse.json(storyboardFixture());
      }),
      http.get("*/api/v1/planning/outlines/:novelId/:chapterId", () => {
        counted();
        return HttpResponse.json({
          id: "outline-1",
          chapter_id: "chapter-1",
          stage_assignment: "act_1",
          outline_notes: "Beat the rival at the ball.",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        });
      }),
      http.get("*/api/v1/novels/:novelId/chapters/chapter-0", () => {
        counted();
        return HttpResponse.json(
          makeChapter({
            id: "chapter-0",
            title: "Cold Open",
            summary: "The rival arrives in town.",
          }),
        );
      }),
      http.get("*/api/v1/novels/:novelId/chapters/chapter-1", () => {
        counted();
        return HttpResponse.json(
          makeChapter({ id: "chapter-1", title: "Ballroom", summary: "The ball begins." }),
        );
      }),
      http.get("*/api/v1/novels/:novelId/chapters/chapter-2", () => {
        counted();
        return HttpResponse.json(
          makeChapter({
            id: "chapter-2",
            title: "Aftermath",
            summary: "The ball ends in scandal.",
          }),
        );
      }),
    );
    harness.render();

    await waitFor(() => {
      expect(screen.getByText("Opening")).toBeDefined();
    });
    // The button has no loading blocker — settle the context fetches first so
    // the assertion is deterministic.
    await waitFor(() => {
      expect(contextGets).toBe(5);
    });
    fireEvent.click(screen.getByText("draftWithAi"));

    await waitFor(() => {
      expect(harness.draftBodies).toHaveLength(1);
    });
    expect(harness.draftBodies[0]).toEqual({
      structure_type: "three_act",
      outline_notes: "Beat the rival at the ball.",
      chapter_summary: "The ball begins.",
      neighbor_summaries:
        'Previous chapter "Cold Open": The rival arrives in town.\nNext chapter "Aftermath": The ball ends in scandal.',
    });
  });

  it("degrades to an empty context body when every source fetch fails", async () => {
    server.use(
      http.get("*/api/v1/planning/storyboard/:novelId", () =>
        HttpResponse.json({}, { status: 500 }),
      ),
      http.get("*/api/v1/planning/outlines/:novelId/:chapterId", () =>
        HttpResponse.json({}, { status: 500 }),
      ),
      http.get("*/api/v1/novels/:novelId/chapters/:chapterId", () =>
        HttpResponse.json({}, { status: 500 }),
      ),
    );
    harness.render();

    await waitFor(() => {
      expect(screen.getByText("Opening")).toBeDefined();
    });
    fireEvent.click(screen.getByText("draftWithAi"));

    await waitFor(() => {
      expect(harness.draftBodies).toHaveLength(1);
    });
    expect(harness.draftBodies[0]).toEqual({});
    // Draft still applies its proposal — graceful, no crash.
    await waitFor(() => {
      expect(harness.putBodies).toHaveLength(1);
    });
  });

  it("omits per-field context when summaries are empty but keeps resolved fields", async () => {
    let contextGets = 0;
    server.use(
      http.get("*/api/v1/planning/storyboard/:novelId", () => {
        contextGets += 1;
        return HttpResponse.json(storyboardFixture());
      }),
      http.get("*/api/v1/planning/outlines/:novelId/:chapterId", () => {
        contextGets += 1;
        return HttpResponse.json({
          id: "outline-1",
          chapter_id: "chapter-1",
          stage_assignment: "act_1",
          outline_notes: "Beat the rival at the ball.",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        });
      }),
      // All chapter summaries empty (never summarized) — must be omitted.
      http.get("*/api/v1/novels/:novelId/chapters/:chapterId", () => {
        contextGets += 1;
        return HttpResponse.json(makeChapter({}));
      }),
    );
    harness.render();

    await waitFor(() => {
      expect(screen.getByText("Opening")).toBeDefined();
    });
    // The button has no loading blocker — settle the context fetches first
    // (storyboard + outline + 3 chapter details) so the click is deterministic.
    await waitFor(() => {
      expect(contextGets).toBe(5);
    });
    fireEvent.click(screen.getByText("draftWithAi"));

    await waitFor(() => {
      expect(harness.draftBodies).toHaveLength(1);
    });
    expect(harness.draftBodies[0]).toEqual({
      structure_type: "three_act",
      outline_notes: "Beat the rival at the ball.",
    });
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
