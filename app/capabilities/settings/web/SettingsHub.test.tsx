// @vitest-environment jsdom
/**
 * The settings area's two doors agree: the hub renders one card per cluster
 * with its description, the layout's nav lists the same destinations, and a
 * card's link really opens the sub-page. The tree under test is the routes
 * this capability actually mounts — the layout, the index and the two
 * children — so a link that resolves only in a stand-in tree cannot pass.
 *
 * The API client is mocked at its module boundary (the provider page mounts
 * its panel here): what the panel says is ProvidersPanel.test.tsx's case,
 * and the requests are the backend's and E2E's to verify.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@shell/lib/i18n";
import { queryClient } from "@shell/lib/query";
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
      case "/api/settings/profiles":
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

describe("the settings area", () => {
  it("lists its clusters in the layout's nav", async () => {
    renderArea("/settings");

    // The nav carries the area's own clusters plus every registry row: the
    // prompts capability contributes its page through the generated
    // registry, so its destination is on the list with no edit to the
    // layout.
    const nav = await screen.findByRole("navigation", { name: t("settings.heading") });
    const destinations = within(nav)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    expect(destinations).toEqual([
      "/settings/language",
      "/settings/provider",
      "/settings/prompts",
    ]);
  });

  it("renders a hub card per cluster with its description and its link", async () => {
    // The cards' words are catalog keys: a missing key must fail here, as
    // the missing key, before a role query can blur the failure.
    expect(t("settings.clusterLanguage")).toBeDefined();
    expect(t("settings.clusterProvider")).toBeDefined();
    expect(t("prompts.settingsTitle")).toBeDefined();

    renderArea("/settings");
    // The shell paints after its settings query answers; the first heading
    // is the gate's opening, and the cards are on that first paint.
    await screen.findByRole("heading", { name: t("settings.heading") });

    const language = screen.getByRole("region", { name: t("settings.clusterLanguage") });
    expect(
      within(language).getByText(t("settings.clusterLanguage.description")),
    ).toBeTruthy();
    expect(within(language).getByRole("link").getAttribute("href")).toBe(
      "/settings/language",
    );

    const provider = screen.getByRole("region", { name: t("settings.clusterProvider") });
    expect(within(provider).getByText(t("settings.clusterProvider.description"))).toBeTruthy();
    expect(within(provider).getByRole("link").getAttribute("href")).toBe(
      "/settings/provider",
    );

    // A contributed row carries no description: the title is the whole
    // card, and the link is the generated registry's path.
    const prompts = screen.getByRole("region", { name: t("prompts.settingsTitle") });
    expect(within(prompts).getByRole("link").getAttribute("href")).toBe("/settings/prompts");
  });

  it("opens the provider cluster from its hub card", async () => {
    renderArea("/settings");
    await screen.findByRole("heading", { name: t("settings.heading") });

    const card = screen.getByRole("region", { name: t("settings.clusterProvider") });
    await userEvent.click(within(card).getByRole("link"));

    // The provider surface mounted: its panel answered the mount's reads
    // with the empty list — and the hub gave way, it did not sit beside it.
    expect(await screen.findByText(t("settings.profiles.empty"))).toBeTruthy();
    expect(
      screen.queryByText(t("settings.clusterLanguage.description")),
    ).toBeNull();
  });
});
