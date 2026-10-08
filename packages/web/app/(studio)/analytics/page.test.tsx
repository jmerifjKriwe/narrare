/**
 * /analytics page tests (STATS-002 Task 16; STATS-001 Task E7 adds Writing).
 *
 * The page owns the section tab bar ("AI Costs" + "Writing" → PanelTabs).
 * Both panels are stubbed here — each has its own suite — so these tests pin
 * the page contract: tab bar composition and that the active panel renders
 * inside the tabpanel. The sidebar analytics entry is verified unit-level,
 * mirroring the Sidebar.scratchpad.test.tsx pattern (link always visible,
 * active state).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "@/components/studio/Sidebar";
import AnalyticsPage from "./page";

// Local next-intl override (replaces the global key-verbatim mock) so the
// tab assertions read like real labels — mirrors AnalyticsCostsPanel.test.
vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => {
    const dict: Record<string, Record<string, string>> = {
      analytics: { sectionLabel: "Analytics" },
      "analytics.costs": { title: "AI Costs" },
      "analytics.writing": { title: "Writing" },
    };
    const messages = dict[namespace] ?? {};
    const t = Object.assign((key: string) => messages[key] ?? key, {
      has: (key: string) => key in messages,
    });
    return t;
  },
}));

// The page composes the panels; their internals (data states, charts) are
// covered by their own suites — stub both at the boundary.
vi.mock("@/components/analytics/AnalyticsCostsPanel", () => ({
  AnalyticsCostsPanel: () => <div data-testid="analytics-costs-panel" />,
}));

vi.mock("@/components/analytics/WritingStatsPanel", () => ({
  WritingStatsPanel: () => <div data-testid="analytics-writing-panel" />,
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
  it("renders the section tab bar (Analytics) with the AI Costs tab selected", () => {
    render(<AnalyticsPage />);

    expect(screen.getByRole("tablist", { name: "Analytics" })).toBeInTheDocument();
    const tab = screen.getByRole("tab", { name: "AI Costs" });
    expect(tab).toHaveAttribute("aria-selected", "true");
  });

  it("offers exactly the Costs and Writing tabs", () => {
    render(<AnalyticsPage />);

    expect(screen.getByTestId("panel-tab-costs")).toBeInTheDocument();
    expect(screen.getByTestId("panel-tab-writing")).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(2);
  });

  it("renders the costs panel inside the tabpanel", () => {
    render(<AnalyticsPage />);

    const panel = screen.getByTestId("analytics-costs-panel");
    expect(screen.getByRole("tabpanel")).toContainElement(panel);
  });

  it("switches to the Writing tab and renders the writing panel", async () => {
    const user = userEvent.setup();
    render(<AnalyticsPage />);

    expect(screen.queryByTestId("analytics-writing-panel")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Writing" }));

    const panel = screen.getByTestId("analytics-writing-panel");
    expect(screen.getByRole("tabpanel")).toContainElement(panel);
    expect(screen.getByRole("tab", { name: "Writing" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByTestId("analytics-costs-panel")).not.toBeInTheDocument();
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
