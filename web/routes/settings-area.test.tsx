// @vitest-environment jsdom
/**
 * The settings area's frame owns the page's shape. Mounted as the layout's
 * Outlet child, a contributed settings page brings sections — an <h2> under
 * the frame's single <h1> — and no container of its own. Over the real
 * composed tree (the shell root, the generated route table — the one place
 * capabilities meet), /settings/prompts must hold exactly one level-1
 * heading, the area's own, and render its body inside the frame's one
 * container: a page container of its own double-insets the area against the
 * cluster nav, and a second <h1> hands a screen reader two page titles for
 * one page. Axe flags neither, so the pin lives here.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { client } from "../lib/api/client";
import { capabilityRoutes } from "../lib/generated/routes";
import { t } from "../lib/i18n";
import { queryClient } from "../lib/query";
import { rootRoute } from "./__root";

vi.mock("../lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<"GET", ReturnType<typeof vi.fn>>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

beforeEach(() => {
  // jsdom implements no scrolling, and the router scrolls on route changes:
  // without this stub each arrival prints jsdom's complaint.
  window.scrollTo = () => {};
  // What the tree asks at /settings/prompts: the shell's locale read (the
  // pre-paint gate), then the page's two reads — the novels list and the
  // prompt summaries, empty here: the shape is the case, not the rows.
  api.GET.mockImplementation(async (path: string) => {
    switch (path) {
      case "/api/settings":
        return { data: { locale: null }, response: ok() };
      case "/api/writing/novels":
        return { data: [], response: ok() };
      case "/api/prompts":
        return { data: [], response: ok() };
      default:
        throw new Error(`unexpected GET ${path}`);
    }
  });
});

afterEach(cleanup);

/** The shell for real — the root route over the generated capability table — entered at `path`. */
function renderAt(path: string): void {
  const router = createRouter({
    routeTree: rootRoute.addChildren(capabilityRoutes),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("the settings area's frame", () => {
  it("owns /settings/prompts' shape: its one <h1>, its one container, the page's <h2> inside", async () => {
    renderAt("/settings/prompts");
    // The page painted: the frame's <h1> and the contributed heading are
    // both on it before the shape is judged.
    await screen.findByRole("heading", { name: t("prompts.heading") });

    // One level-1 heading, and it is the area's own — a contributed page
    // speaks at <h2> and below, the level the hub's cards already use.
    const levelOne = screen.getAllByRole("heading", { level: 1 });
    expect(levelOne).toHaveLength(1);
    expect(levelOne[0].textContent).toBe(t("settings.heading"));

    // The frame's one container: a contributed page's own container would
    // sit inside it and double the horizontal inset. The container classes
    // are the DOM witness — a page that brings its own `mx-auto max-w-2xl`
    // is exactly the regression this names.
    const containers = document.querySelectorAll("main .mx-auto.max-w-2xl");
    expect(containers).toHaveLength(1);
    expect(
      within(containers[0] as HTMLElement).getByRole("heading", {
        level: 2,
        name: t("prompts.heading"),
      }),
    ).toBeTruthy();
  });
});
