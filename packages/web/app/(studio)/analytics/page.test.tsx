/**
 * /analytics page tests (STATS-002, Task 16).
 *
 * The page owns the section tab bar (v1: single "AI Costs" tab →
 * AnalyticsCostsPanel; STATS-001 adds more tabs later). The panel itself is
 * stubbed here — it has its own suite — so these tests pin the page contract:
 * tab bar composition and that the panel renders inside the tabpanel.
 * The sidebar analytics entry is verified unit-level, mirroring the
 * Sidebar.scratchpad.test.tsx pattern (link always visible, active state).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "@/components/studio/Sidebar";
import AnalyticsPage from "./page";

// Local next-intl override (replaces the global key-verbatim mock) so the
// tab assertions read like real labels — mirrors AnalyticsCostsPanel.test.
vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const dict: Record<string, Record<string, string>> = {
      "analytics.costs": { title: "AI Costs" },
    };
    const messages = dict[namespace] ?? {};
    const t = Object.assign((key: string) => messages[key] ?? key, {
      has: (key: string) => key in messages,
    });
    return t;
  },
}));

// The page composes the panel; the panel's internals (data states, charts)
// are covered by AnalyticsCostsPanel.test.tsx — stub it at the boundary.
vi.mock("@/components/analytics/AnalyticsCostsPanel", () => ({
  AnalyticsCostsPanel: () => <div data-testid="analytics-costs-panel" />,
}));

// Local next/navigation override (mutable pathname, mirrors the global mock's
// shape — useParams keeps the WITH-novel case; see Sidebar.scratchpad.test).
const navigationMocks = vi.hoisted(() => ({ pathname: "/" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  useParams: () => ({ id: "novel-1" }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => navigationMocks.pathname,
}));

// Sidebar queries react-query against MSW (auth/me etc.) — repo-standard
// test wrapper (see Sidebar.scratchpad.test.tsx).
function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("AnalyticsPage", () => {
  it("renders the AI Costs tab selected in an accessible tab bar", () => {
    render(<AnalyticsPage />);

    expect(screen.getByRole("tablist", { name: "AI Costs" })).toBeInTheDocument();
    const tab = screen.getByRole("tab", { name: "AI Costs" });
    expect(tab).toHaveAttribute("aria-selected", "true");
  });

  it("renders the costs panel inside the tabpanel", () => {
    render(<AnalyticsPage />);

    const panel = screen.getByTestId("analytics-costs-panel");
    expect(screen.getByRole("tabpanel")).toContainElement(panel);
  });
});

describe("Sidebar analytics entry", () => {
  it("renders the analytics link pointing at /analytics", async () => {
    renderWithProviders(<Sidebar />);

    const link = await screen.findByTestId("sidebar-analytics-link");
    expect(link).toHaveAttribute("href", "/analytics");
  });

  it("highlights on /analytics and stays inactive on other routes", async () => {
    navigationMocks.pathname = "/analytics";
    const { unmount } = renderWithProviders(<Sidebar />);

    const link = await screen.findByTestId("sidebar-analytics-link");
    expect(link).toHaveAttribute("aria-current", "page");
    expect(link.className).toContain("bg-primary");
    expect(link.className).toContain("text-primary-foreground");
    unmount();

    navigationMocks.pathname = "/novel/novel-1";
    renderWithProviders(<Sidebar />);
    const inactive = await screen.findByTestId("sidebar-analytics-link");
    expect(inactive.className).not.toContain("bg-primary");
    expect(inactive.className).toContain("hover:bg-accent");
    expect(inactive).not.toHaveAttribute("aria-current");
  });
});
