/**
 * BaendeList component tests (Spec 1, Slice 4, Task 4.7).
 *
 * The Bände list renders the novels in a Series (ordered by series_position)
 * with position pills, a link to each novel, an is_demo badge, and up/down
 * reorder controls. The "Add Novel" flow is delegated to AddNovelToSeries,
 * which is mocked here (it has its own suite) so these tests isolate the list
 * + reorder behavior.
 *
 * Conventions (mirrors VolumeManagementView.test.tsx): the centralized
 * setupTests.ts mock returns i18n KEY STRINGS verbatim, so assertions check for
 * keys. A per-file QueryClientProvider wrapper is used because this component
 * owns a useQuery (novels-in-series) + a reorder useMutation.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BaendeList } from "@/components/series/BaendeList";
import type { NovelSummary } from "@/types";

// --- Hoisted mock state ------------------------------------------------------
const { mockListNovels, mockReorderNovels } = vi.hoisted(() => ({
  mockListNovels: vi.fn(),
  mockReorderNovels: vi.fn(),
}));

vi.mock("@/lib/api/series", () => ({
  seriesApi: {
    listNovels: (...args: unknown[]) => mockListNovels(...args),
    reorderNovels: (...args: unknown[]) => mockReorderNovels(...args),
  },
}));

// AddNovelToSeries has its own suite — stub it here to isolate the list.
vi.mock("@/components/series/AddNovelToSeries", () => ({
  AddNovelToSeries: () => <div data-testid="add-novel-to-series-stub" />,
}));

// BandSummaryCard has its own suite — stub it here to isolate the list. The
// stub echoes the novelId prop so the integration test can assert per-row wiring.
vi.mock("@/components/series/BandSummaryCard", () => ({
  BandSummaryCard: ({ novelId }: { novelId: string }) => (
    <div data-testid={`band-summary-card-stub-${novelId}`} />
  ),
}));

// --- Fixtures ----------------------------------------------------------------
const novels: NovelSummary[] = [
  {
    id: "novel-1",
    series_id: "series-1",
    title: "Leviathan Wakes",
    author: "Corey",
    genre: "sci-fi",
    writing_language: "en",
    is_demo: false,
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "novel-2",
    series_id: "series-1",
    title: "Caliban's War",
    author: "Corey",
    genre: "sci-fi",
    writing_language: "en",
    is_demo: true,
    updated_at: "2026-01-02T00:00:00Z",
  },
];

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("BaendeList", () => {
  beforeEach(() => {
    mockListNovels.mockResolvedValue(novels);
    mockReorderNovels.mockResolvedValue(undefined);
  });

  it("shows a loading state while the novels are loading", () => {
    mockListNovels.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<BaendeList seriesId="series-1" />);
    expect(screen.getByTestId("baende-list-loading")).toBeDefined();
  });

  it("renders one row per novel in series order", async () => {
    renderWithProviders(<BaendeList seriesId="series-1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("baende-novel-row")).toHaveLength(2);
    });
    expect(screen.getByText("Leviathan Wakes")).toBeDefined();
    expect(screen.getByText("Caliban's War")).toBeDefined();
  });

  it("shows a 1-based position pill for each novel", async () => {
    renderWithProviders(<BaendeList seriesId="series-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("baende-position-0").textContent?.trim()).toBe("1");
      expect(screen.getByTestId("baende-position-1").textContent?.trim()).toBe("2");
    });
  });

  it("links each title to the novel route", async () => {
    renderWithProviders(<BaendeList seriesId="series-1" />);
    await waitFor(() => {
      expect(screen.getByText("Leviathan Wakes").getAttribute("href")).toBe("/novel/novel-1");
    });
    expect(screen.getByText("Caliban's War").getAttribute("href")).toBe("/novel/novel-2");
  });

  it("renders the is_demo badge only for demo novels", async () => {
    renderWithProviders(<BaendeList seriesId="series-1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("baende-novel-row")).toHaveLength(2);
    });
    expect(screen.getAllByText("series.baende.demoBadge")).toHaveLength(1);
  });

  it("shows an empty state when the series has no novels", async () => {
    mockListNovels.mockResolvedValue([]);
    renderWithProviders(<BaendeList seriesId="series-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("baende-list-empty")).toBeDefined();
    });
  });

  it("reorders up when the up button on a non-first row is clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<BaendeList seriesId="series-1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("baende-novel-row")).toHaveLength(2);
    });

    // Click "up" on the second row → swaps novel-2 and novel-1.
    const upButtons = screen.getAllByLabelText("series.baende.reorderUp");
    await user.click(upButtons[1]);

    expect(mockReorderNovels).toHaveBeenCalledWith("series-1", ["novel-2", "novel-1"]);
  });

  it("reorders down when the down button on a non-last row is clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<BaendeList seriesId="series-1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("baende-novel-row")).toHaveLength(2);
    });

    const downButtons = screen.getAllByLabelText("series.baende.reorderDown");
    await user.click(downButtons[0]);

    expect(mockReorderNovels).toHaveBeenCalledWith("series-1", ["novel-2", "novel-1"]);
  });

  it("disables up on the first row and down on the last row", async () => {
    renderWithProviders(<BaendeList seriesId="series-1" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("baende-novel-row")).toHaveLength(2);
    });

    const upButtons = screen.getAllByLabelText("series.baende.reorderUp") as HTMLButtonElement[];
    const downButtons = screen.getAllByLabelText(
      "series.baende.reorderDown",
    ) as HTMLButtonElement[];
    expect(upButtons[0].disabled).toBe(true);
    expect(downButtons[1].disabled).toBe(true);
    expect(upButtons[1].disabled).toBe(false);
    expect(downButtons[0].disabled).toBe(false);
  });
});
