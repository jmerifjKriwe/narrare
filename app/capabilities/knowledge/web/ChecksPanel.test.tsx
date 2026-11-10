// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { client } from "@shell/lib/api/client";
import { t } from "@shell/lib/i18n";
import { rootRoute } from "@shell/routes/__root";
import { ChecksPanel } from "./ChecksPanel";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

const api = client as unknown as {
  GET: ReturnType<typeof vi.fn>;
  POST: ReturnType<typeof vi.fn>;
};

const finding = {
  id: "finding-1",
  novel_id: "novel",
  summary: "Mira: 34 vs. 37",
  detail: '"Mira ist 34" vs. "Mira ist 37"',
  status: "pending",
  created_at: "2026-01-01T00:00:00Z",
};

function renderPanel() {
  const novel = createRoute({
    getParentRoute: () => rootRoute,
    path: "/novels/$id",
    component: ChecksPanel,
  });
  const router = createRouter({
    routeTree: rootRoute.addChildren([novel]),
    history: createMemoryHistory({ initialEntries: ["/novels/novel"] }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider>);
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("ChecksPanel finding card", () => {
  it("states the finding on Panel primitives: the summary as heading, the evidence, both decisions", async () => {
    // The card is the dock's own surface (Panel + shell Buttons), not the
    // proposal card: the finding heads it as a heading, the evidence rides
    // along, and both decisions stand on Buttons.
    api.GET.mockResolvedValue({ data: [finding], response: { ok: true } });
    renderPanel();

    expect(await screen.findByRole("heading", { name: finding.summary })).toBeTruthy();
    expect(screen.getByText(finding.detail)).toBeTruthy();
    expect(screen.getByRole("button", { name: t("proposal.accept") })).toBeTruthy();
    expect(screen.getByRole("button", { name: t("proposal.discard") })).toBeTruthy();
  });

  it("names each finding region with the finding's own summary", async () => {
    // Sibling findings share one title key — the region name carries the
    // summary, so a region list tells the contradictions apart.
    api.GET.mockResolvedValue({ data: [finding], response: { ok: true } });
    renderPanel();

    expect(
      await screen.findByRole("region", {
        name: `${t("knowledge.findingTitle")}: ${finding.summary}`,
      }),
    ).toBeTruthy();
  });
});
