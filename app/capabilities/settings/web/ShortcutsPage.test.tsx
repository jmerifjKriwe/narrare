// @vitest-environment jsdom
/**
 * The shortcuts cluster is a read-only map of the registry: one row per
 * entry, grouped by the scope it applies in, with the platform's own keycap
 * — and one honest line that remapping is not available yet.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@shell/lib/i18n";
import { queryClient } from "@shell/lib/query";
import { SHORTCUTS, shortcutKeycap } from "@shell/lib/shortcuts";
import { rootRoute } from "@shell/routes/__root";

vi.mock("@shell/lib/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

import { client } from "@shell/lib/api/client";

import { routes } from "./routes";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<"GET", ReturnType<typeof vi.fn>>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The area over its real routes, entered at `path`, inside the shell they parent at. */
function renderArea(path: string): void {
  const router = createRouter({
    routeTree: rootRoute.addChildren(routes),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  // jsdom implements no scrolling, and the router scrolls on every route
  // change: without this stub each navigation prints jsdom's complaint.
  window.scrollTo = () => {};
  api.GET.mockImplementation(async (path: string) => {
    switch (path) {
      case "/api/settings/providers":
        return { data: [], response: ok() };
      case "/api/settings/models":
        return { data: [], response: ok() };
      case "/api/settings/assignments":
        return { data: [], response: ok() };
      case "/api/settings/tasks":
        return { data: [], response: ok() };
      default:
        // The shell's own locale read lands here too; its query treats any
        // failure as "the browser decides" and opens the pre-paint gate.
        throw new Error(`unexpected GET ${path}`);
    }
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("the shortcuts cluster", () => {
  it("renders one row per registry entry, grouped by scope, with the registry's keycap", async () => {
    renderArea("/settings/shortcuts");
    await screen.findByRole("heading", { name: t("settings.clusterShortcuts") });

    // One row per entry — the map is complete exactly when nothing is
    // missing and nothing extra stands beside it.
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(SHORTCUTS.length);

    for (const entry of SHORTCUTS) {
      const row = rows.find((candidate) => candidate.textContent?.includes(t(entry.labelKey)));
      expect(row, entry.id).toBeDefined();
      expect(row?.textContent).toContain(shortcutKeycap(entry.id));
    }

    // Each scope the registry uses owns a group the rows stand in.
    for (const scope of ["global", "workspace", "editor"] as const) {
      const entries = SHORTCUTS.filter((entry) => entry.scope === scope);
      if (entries.length === 0) continue;
      const group = await screen.findByRole("region", {
        name: t(`settings.shortcuts.${scope}`),
      });
      for (const entry of entries) {
        expect(
          within(group).getByText(t(entry.labelKey)),
          `${scope}/${entry.id}`,
        ).toBeTruthy();
      }
    }
  });

  it("says remapping is not available yet", async () => {
    renderArea("/settings/shortcuts");
    await screen.findByText(t("settings.shortcuts.note"));
  });
});
