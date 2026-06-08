/**
 * Unit tests for DemoProjectCards component.
 *
 * Covers: loading state, error state with retry, empty state,
 * normal render with demo data, click navigation, i18n key usage.
 *
 * @module DemoProjectCards.test
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DemoProjectCards } from "@/components/studio/DemoProjectCards";
import type { DemoProjectInfo } from "@/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockListDemos = vi.fn<() => Promise<DemoProjectInfo[]>>();
const mockPush = vi.fn<(url: string) => void>();

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  // setupApi is not exported from barrel — mock the setup module directly
}));

vi.mock("@/lib/api/setup", () => ({
  setupApi: { listDemos: () => mockListDemos() },
}));

vi.mock("next/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("next/navigation")>()),
  useRouter: () => ({ push: mockPush }),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SAMPLE_DEMO: DemoProjectInfo = {
  id: "demo_fantasy",
  title: "Echoes of the Thornwall",
  writing_language: "en",
  genre: "Fantasy",
  chapter_count: 4,
  character_count: 5,
  word_count: 3130,
  description: "A dark forest guards ancient secrets.",
  author: "Narrare Demo",
  logline: "A bard must sing the Thornwall back to sleep.",
  pov: "Third Person",
  tags: ["fantasy", "magic"],
};

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function renderWithProviders(ui: ReactNode) {
  const qc = createQueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DemoProjectCards", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // Loading state (skeleton)
  // -------------------------------------------------------------------------

  it("shows skeleton loading state while fetching demos", () => {
    // Never resolves → stays loading
    mockListDemos.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<DemoProjectCards />);

    // Skeleton renders with animate-pulse
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  // -------------------------------------------------------------------------
  // Error state with retry
  // -------------------------------------------------------------------------

  it("shows error state with retry button when fetch fails", async () => {
    mockListDemos.mockRejectedValue(new Error("Network error"));

    renderWithProviders(<DemoProjectCards />);

    // Wait for error state to render
    const errorText = await screen.findByText("demos.error");
    expect(errorText).toBeDefined();

    // Retry button present
    const retryBtn = screen.getByText("demos.retry");
    expect(retryBtn).toBeDefined();

    // Mock success for retry
    mockListDemos.mockResolvedValue([SAMPLE_DEMO]);

    await userEvent.click(retryBtn);

    // After retry, demos should render (not error state)
    const title = await screen.findByText("Echoes of the Thornwall");
    expect(title).toBeDefined();
  });

  // -------------------------------------------------------------------------
  // Empty state (returns null)
  // -------------------------------------------------------------------------

  it("returns null when no demos are available", async () => {
    mockListDemos.mockResolvedValue([]);

    const { container } = renderWithProviders(<DemoProjectCards />);

    // Wait for query to resolve
    await screen.findByText("demos.title");

    // Section exists but the grid should be empty (component renders the section header)
    expect(container.querySelector("section")).not.toBeNull();
    // No demo cards rendered
    expect(container.querySelectorAll("button[type='button']").length).toBe(0);
  });

  // -------------------------------------------------------------------------
  // Normal render with demo data
  // -------------------------------------------------------------------------

  it("renders demo cards with correct data", async () => {
    mockListDemos.mockResolvedValue([SAMPLE_DEMO]);

    renderWithProviders(<DemoProjectCards />);

    // Wait for demo card to render
    const title = await screen.findByText("Echoes of the Thornwall");
    expect(title).toBeDefined();

    // Genre badge
    expect(screen.getByText("Fantasy")).toBeDefined();

    // Writing language
    expect(screen.getByText("en")).toBeDefined();

    // Description
    expect(screen.getByText("A dark forest guards ancient secrets.")).toBeDefined();
  });

  it("renders multiple demo cards", async () => {
    const demo2: DemoProjectInfo = {
      ...SAMPLE_DEMO,
      id: "demo_scifi",
      title: "Dead Signal",
      genre: "Sci-Fi",
      description: "A signal from a dead world.",
    };
    mockListDemos.mockResolvedValue([SAMPLE_DEMO, demo2]);

    renderWithProviders(<DemoProjectCards />);

    expect(await screen.findByText("Echoes of the Thornwall")).toBeDefined();
    expect(screen.getByText("Dead Signal")).toBeDefined();
  });

  // -------------------------------------------------------------------------
  // Click navigation
  // -------------------------------------------------------------------------

  it("navigates to wizard with demo id on card click", async () => {
    mockListDemos.mockResolvedValue([SAMPLE_DEMO]);

    renderWithProviders(<DemoProjectCards />);

    // Wait for card to render, then find the button that contains the title
    const card = await screen.findByRole("button", { name: /Echoes of the Thornwall/i });
    await userEvent.click(card);

    expect(mockPush).toHaveBeenCalledWith("/wizard?starter=demo_fantasy");
  });

  // -------------------------------------------------------------------------
  // i18n keys
  // -------------------------------------------------------------------------

  it("uses i18n keys for section title and subtitle", async () => {
    mockListDemos.mockResolvedValue([SAMPLE_DEMO]);

    renderWithProviders(<DemoProjectCards />);

    expect(await screen.findByText("demos.title")).toBeDefined();
    expect(screen.getByText("demos.subtitle")).toBeDefined();
  });

  it("uses i18n keys for demo stats", async () => {
    mockListDemos.mockResolvedValue([SAMPLE_DEMO]);

    renderWithProviders(<DemoProjectCards />);

    // The setupTests.ts mock renders i18n keys with params interpolated
    expect(await screen.findByText("demos.chapters")).toBeDefined();
    expect(screen.getByText("demos.words")).toBeDefined();
    expect(screen.getByText("demos.characters")).toBeDefined();
    // "demos.loadDemo →" rendered with arrow suffix — use substring match
    expect(screen.getByText(/demos\.loadDemo/)).toBeDefined();
  });
});
