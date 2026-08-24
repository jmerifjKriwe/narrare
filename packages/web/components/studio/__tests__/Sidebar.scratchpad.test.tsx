/**
 * Sidebar scratchpad entry (NOTES-001 §7): the global nav link renders
 * regardless of novel selection and points at /scratchpad, and the paired
 * quick-capture trigger opens the QuickCaptureProvider panel (T29).
 * P-FE2: the entry highlights when the current pathname IS /scratchpad
 * (active styling mirroring SidebarNav) and not otherwise.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QuickCaptureProvider } from "@/components/notes/QuickCaptureProvider";
import { Sidebar } from "../Sidebar";

// Local next/navigation override (mutable pathname, mirrors the global mock's
// shape — useParams keeps the WITH-novel case; see setupTests note there).
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

// Default MSW handlers already serve GET /api/v1/auth/me.
// NOTE: the setupTests next/navigation mock makes useParams() return
// { id: "novel-1" } — so these tests exercise the WITH-novel case; the
// link's always-visible placement (outside SidebarNav's novelId guard)
// structurally covers the no-novel case.
//
// Sidebar uses real react-query against MSW (auth/me, chapters, KB badge),
// so it needs a QueryClientProvider — repo-standard test wrapper
// (see SessionPanel.test.tsx / GenerationPanel.test.tsx).

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("Sidebar scratchpad entry", () => {
  it("renders the scratchpad link on every page load", async () => {
    renderWithProviders(<Sidebar />);
    const link = await screen.findByTestId("sidebar-scratchpad-link");
    expect(link).toHaveAttribute("href", "/scratchpad");
  });

  it("renders alongside the novel-scoped nav items", async () => {
    renderWithProviders(<Sidebar />);
    expect(await screen.findByTestId("sidebar-scratchpad-link")).toBeInTheDocument();
    // With the mocked params (id "novel-1") the novel nav is present too.
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
  });
});

describe("Sidebar quick-capture button", () => {
  it("opens the quick capture panel from the sidebar", () => {
    // The provider renders inside QueryClientProvider (renderWithProviders)
    // because the panel mounts useCreateNote (T28 constraint).
    renderWithProviders(
      <QuickCaptureProvider>
        <Sidebar />
      </QuickCaptureProvider>,
    );
    fireEvent.click(screen.getByTestId("sidebar-quick-capture-button"));
    expect(screen.getByTestId("quick-capture-panel")).toBeInTheDocument();
  });
});

describe("Sidebar scratchpad active state (P-FE2)", () => {
  it("applies the active visual language when pathname is /scratchpad", async () => {
    navigationMocks.pathname = "/scratchpad";
    renderWithProviders(<Sidebar />);
    const link = await screen.findByTestId("sidebar-scratchpad-link");
    // Mirrors SidebarNav's active classes (bg-primary text-primary-foreground
    // shadow-sm) and marks the current page semantically.
    expect(link.className).toContain("bg-primary");
    expect(link.className).toContain("text-primary-foreground");
    expect(link).toHaveAttribute("aria-current", "page");
  });

  it("stays in the inactive state on other routes", async () => {
    navigationMocks.pathname = "/novel/novel-1";
    renderWithProviders(<Sidebar />);
    const link = await screen.findByTestId("sidebar-scratchpad-link");
    expect(link.className).not.toContain("bg-primary");
    expect(link.className).toContain("hover:bg-accent");
    expect(link).not.toHaveAttribute("aria-current");
  });
});
