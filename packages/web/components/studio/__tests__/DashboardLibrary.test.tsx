/**
 * DashboardLibrary tests — the mixed Series + Standalone grid
 * (Spec 1, Slice 4, Task 4.5).
 *
 * Covers the N2 dashboard behaviour:
 *   - series cards and standalone novel cards render together in one grid,
 *   - novels that belong to a series are excluded from the standalone grid,
 *   - combined loading skeleton + empty hint,
 *   - the "New Series" and "New Novel" entry points are always reachable,
 *   - click wiring (open series / new series / new novel).
 *
 * Conventions (mirrors SeriesCard / DashboardView tests): the centralized
 * setupTests.ts mock returns i18n KEY STRINGS verbatim, so assertions check
 * for keys (e.g. "dashboard.newNovel") rather than translated values.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DashboardLibrary } from "@/components/studio/DashboardLibrary";
import type { NovelSummary, SeriesSummary } from "@/types";

const seriesFixture: SeriesSummary = {
  id: "s1",
  title: "The Expanse",
  subtitle: null,
  status: "active",
  novel_count: 4,
};

const standaloneNovel: NovelSummary = {
  id: "n1",
  title: "Standalone Book",
  author: "Author",
  genre: "Fantasy",
  writing_language: "en",
  is_demo: false,
  updated_at: "2024-01-01",
  series_id: null,
};

const memberNovel: NovelSummary = {
  ...standaloneNovel,
  id: "n2",
  title: "Member Novel",
  series_id: "s1",
};

const handlers = {
  onOpenSeries: vi.fn(),
  onNewSeries: vi.fn(),
  onDeleteNovel: vi.fn(),
  onEditNovel: vi.fn(),
  onNewNovel: vi.fn(),
  onExportNovel: vi.fn(),
  isDeleting: false,
  formatDate: (d: string) => d,
};

describe("DashboardLibrary", () => {
  it("renders series cards and standalone novel cards in one grid", () => {
    render(
      <DashboardLibrary
        series={[seriesFixture]}
        novels={[standaloneNovel]}
        isLoading={false}
        {...handlers}
      />,
    );
    expect(screen.getByTestId("series-card")).toBeDefined();
    expect(screen.getAllByTestId("novel-card")).toHaveLength(1);
  });

  it("excludes novels that belong to a series from the standalone grid", () => {
    render(
      <DashboardLibrary
        series={[seriesFixture]}
        novels={[standaloneNovel, memberNovel]}
        isLoading={false}
        {...handlers}
      />,
    );
    // Only the standalone novel renders as a novel card.
    expect(screen.getAllByTestId("novel-card")).toHaveLength(1);
    expect(screen.queryByText("Member Novel")).toBeNull();
  });

  it("shows the loading skeleton and no cards while loading", () => {
    render(
      <DashboardLibrary
        series={[seriesFixture]}
        novels={[standaloneNovel]}
        isLoading={true}
        {...handlers}
      />,
    );
    expect(screen.queryByTestId("series-card")).toBeNull();
    expect(screen.queryByTestId("novel-card")).toBeNull();
  });

  it("shows the empty hint when there are no series and no novels", () => {
    render(<DashboardLibrary series={[]} novels={[]} isLoading={false} {...handlers} />);
    expect(screen.getByText("dashboard.emptyTitle")).toBeDefined();
    expect(screen.getByText("dashboard.emptySubtitle")).toBeDefined();
  });

  it("always renders the New Series and New Novel entry points", () => {
    render(<DashboardLibrary series={[]} novels={[]} isLoading={false} {...handlers} />);
    expect(screen.getByTestId("new-series-btn")).toBeDefined();
    expect(screen.getByTestId("new-novel-btn")).toBeDefined();
  });

  it("calls onOpenSeries with the id when a series card is clicked", () => {
    const onOpenSeries = vi.fn();
    render(
      <DashboardLibrary
        series={[seriesFixture]}
        novels={[]}
        isLoading={false}
        {...handlers}
        onOpenSeries={onOpenSeries}
      />,
    );
    fireEvent.click(screen.getByTestId("series-card"));
    expect(onOpenSeries).toHaveBeenCalledWith("s1");
  });

  it("calls onNewSeries when the New Series card is clicked", () => {
    const onNewSeries = vi.fn();
    render(
      <DashboardLibrary
        series={[]}
        novels={[]}
        isLoading={false}
        {...handlers}
        onNewSeries={onNewSeries}
      />,
    );
    fireEvent.click(screen.getByTestId("new-series-btn"));
    expect(onNewSeries).toHaveBeenCalledOnce();
  });

  it("calls onNewNovel when the New Novel card is clicked", () => {
    const onNewNovel = vi.fn();
    render(
      <DashboardLibrary
        series={[]}
        novels={[]}
        isLoading={false}
        {...handlers}
        onNewNovel={onNewNovel}
      />,
    );
    fireEvent.click(screen.getByTestId("new-novel-btn"));
    expect(onNewNovel).toHaveBeenCalledOnce();
  });
});
