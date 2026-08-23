/**
 * Sidebar scratchpad entry (NOTES-001 §7): the global nav link renders
 * regardless of novel selection and points at /scratchpad.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Sidebar } from "../Sidebar";

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
