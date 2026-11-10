// @vitest-environment jsdom
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRoute, createRouter, Outlet, RouterProvider } from "@tanstack/react-router";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@shell/lib/api/client";
import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";
import { SceneDock } from "./SceneDock";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), PUT: vi.fn() },
}));

const api = client as unknown as {
  GET: ReturnType<typeof vi.fn>;
  PUT: ReturnType<typeof vi.fn>;
};

const NOVEL_ID = "novel-1";
const CHAPTER_ID = "chapter-1";

function scene(id: string, title: string, status = "planned", position = 1) {
  return {
    id,
    chapter_id: CHAPTER_ID,
    position,
    title,
    purpose: `wozu ${title}`,
    conflict: `was ${title}`,
    resolution: `wie ${title}`,
    beats: [`${title} eins`],
    status,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function aggregate(scenes: ReturnType<typeof scene>[]) {
  return {
    chapter_id: CHAPTER_ID,
    scenes,
    version_updated_at: "2026-01-02T00:00:00Z",
  };
}

function mockPutEcho() {
  api.PUT.mockImplementation(async (_path: string, options: { body: { scenes: unknown[] } }) => ({
    data: { chapter_id: CHAPTER_ID, scenes: options.body.scenes, version_updated_at: "2026-01-03T00:00:00Z" },
    response: { ok: true },
  }));
}
function mockAggregate(scenes: ReturnType<typeof scene>[]) {
  api.GET.mockImplementation(async (path: string) => {
    if (typeof path === "string" && path.includes("/planning/")) {
      return { data: aggregate(scenes), response: { ok: true } };
    }
    return {
      data: [
        {
          id: CHAPTER_ID,
          novel_id: NOVEL_ID,
          title: "Ankunft",
          body: "",
          position: 0,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-02T00:00:00Z",
        },
      ],
      response: { ok: true },
    };
  });
}

function renderDock() {
  const novel = createRoute({
    getParentRoute: () => rootRoute,
    path: "/novels/$id",
    component: Outlet,
  });
  const planning = createRoute({
    getParentRoute: () => novel,
    path: "planning",
    component: SceneDock,
  });
  const router = createRouter({
    routeTree: rootRoute.addChildren([novel.addChildren([planning])]),
    history: createMemoryHistory({
      initialEntries: [`/novels/${NOVEL_ID}/planning?chapter=${CHAPTER_ID}`],
    }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  queryClient.clear();
});

describe("SceneDock list", () => {
  it("renders the chapter's scenes with their statuses", async () => {
    mockAggregate([scene("s1", "Anfang"), scene("s2", "Mitte", "in_progress", 2)]);
    renderDock();

    expect(await screen.findByRole("group", { name: "Anfang" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "Mitte" })).toBeTruthy();
    expect(screen.getByText("Planned")).toBeTruthy();
    expect(screen.getByText("In progress")).toBeTruthy();
    // The save stands down on a clean list: nothing to write.
    expect(screen.getByRole("button", { name: "Save scenes" })).toHaveProperty("disabled", true);
  });

  it("advances a scene's status through the mocked PUT", async () => {
    const scenes = [scene("s1", "Anfang"), scene("s2", "Mitte", "in_progress", 2)];
    mockAggregate(scenes);
    mockPutEcho();
    renderDock();
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    // Planned becomes in progress, and the save carries the new status.
    const first = await screen.findByRole("group", { name: "Anfang" });
    await user.click(within(first).getByRole("button", { name: "Advance to In progress" }));
    expect(within(first).getByText("In progress")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Save scenes" }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalledTimes(1));
    const body = api.PUT.mock.calls[0]?.[1] as { body: { scenes: { status: string }[] } };
    expect(body.body.scenes.map((row) => row.status)).toEqual(["in_progress", "in_progress"]);

    // In progress becomes complete through the same save.
    const second = screen.getByRole("group", { name: "Mitte" });
    await user.click(within(second).getByRole("button", { name: "Advance to Complete" }));
    await user.click(screen.getByRole("button", { name: "Save scenes" }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalledTimes(2));
    const again = api.PUT.mock.calls[1]?.[1] as { body: { scenes: { status: string }[] } };
    expect(again.body.scenes.map((row) => row.status)).toEqual(["in_progress", "complete"]);

    // Complete is the end of the lifecycle: no advance stands beside it.
    expect(
      within(screen.getByRole("group", { name: "Mitte" })).queryByRole("button", {
        name: /Advance to/,
      }),
    ).toBeNull();
  });
});

describe("SceneDock dirty model", () => {
  it("marks add, reorder and delete dirty and saves the whole list in order", async () => {
    const scenes = [scene("s1", "Anfang"), scene("s2", "Mitte", "planned", 2)];
    mockAggregate(scenes);
    mockPutEcho();
    renderDock();
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    await screen.findByRole("group", { name: "Anfang" });

    // Add: the untitled row joins the end and the save wakes.
    await user.click(screen.getByRole("button", { name: "Add scene" }));
    const added = screen.getByRole("group", { name: "Untitled scene" });
    expect(screen.getByText("Unsaved changes.")).toBeTruthy();

    // Reorder: the new row moves above Anfang.
    await user.click(within(added).getByRole("button", { name: "Move up" }));
    await user.click(within(added).getByRole("button", { name: "Move up" }));
    const titles = screen
      .getAllByRole("group", { name: /Anfang|Mitte|Untitled scene/ })
      .map((group) => group.getAttribute("aria-label"));
    expect(titles[0]).toBe("Untitled scene");

    // Delete: Mitte leaves the list.
    await user.click(
      within(screen.getByRole("group", { name: "Mitte" })).getByRole("button", {
        name: "Delete scene",
      }),
    );
    expect(screen.queryByRole("group", { name: "Mitte" })).toBeNull();

    // The save is the whole list in its new order: the untitled creation
    // carries a client-generated id, Anfang follows it.
    await user.click(screen.getByRole("button", { name: "Save scenes" }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalledTimes(1));
    const body = api.PUT.mock.calls[0]?.[1] as {
      body: { scenes: { id: string; title: string }[] };
    };
    expect(body.body.scenes.map((row) => row.title)).toEqual(["", "Anfang"]);
    expect(body.body.scenes[0]?.id).toBeTruthy();
    // The save settled: the guard sleeps again.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save scenes" })).toHaveProperty(
        "disabled",
        true,
      ),
    );
    expect(screen.queryByText("Unsaved changes.")).toBeNull();
  });

  it("names a refused save and retries it", async () => {
    mockAggregate([scene("s1", "Anfang")]);
    api.PUT.mockResolvedValue({
      data: undefined,
      error: { detail: "unknown scene id: 00000000-0000-0000-0000-000000000000" },
      response: { ok: false, status: 422 },
    });
    renderDock();
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    const first = await screen.findByRole("group", { name: "Anfang" });
    await user.type(within(first).getByRole("textbox", { name: "Title of scene 1" }), "!");
    await user.click(screen.getByRole("button", { name: "Save scenes" }));

    // The refusal is the dock's own Notice, with the server's words and a
    // way back that is the same save again.
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Saving failed: unknown scene id:");
    await user.click(within(alert).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(api.PUT).toHaveBeenCalledTimes(2));
    // Still refused, still dirty: the words stay where the writer left them.
    expect(screen.getByRole("textbox", { name: "Title of scene 1" })).toHaveProperty(
      "value",
      "Anfang!",
    );
  });
});

describe("SceneDock leave guard", () => {
  it("asks before a navigation throws away unsaved scenes", async () => {
    mockAggregate([scene("s1", "Anfang")]);
    const router = renderDock();
    const user = userEvent.setup({ pointerEventsCheck: 0 });

    const first = await screen.findByRole("group", { name: "Anfang" });
    await user.type(within(first).getByRole("textbox", { name: "Title of scene 1" }), "!");

    // Closing the dock is a navigation to the workspace: the guard asks. The
    // navigation is fired, not awaited — a blocked navigation only settles
    // once the ask is answered, so awaiting it here would deadlock the test.
    await act(async () => {
      void router.navigate({ to: "/novels/$id", params: { id: NOVEL_ID } });
    });
    const dialog = await screen.findByRole("dialog", { name: "Unsaved text" });
    expect(
      within(dialog).getByText("This form has changes that were not saved. Leave anyway?"),
    ).toBeTruthy();

    // Staying keeps the dock and the words.
    await user.click(within(dialog).getByRole("button", { name: "Stay" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByRole("group", { name: "Anfang!" })).toBeTruthy();
    expect(router.state.location.pathname).toContain("/planning");
  });
});
