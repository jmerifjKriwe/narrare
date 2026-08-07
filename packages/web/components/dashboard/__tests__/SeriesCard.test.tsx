/**
 * SeriesCard component tests — dashboard card for a Series
 * (Spec 1, Slice 4, Task 4.4).
 *
 * Covers: title + novel-count render, subtitle (present/absent), status badge,
 * click → onClick(id), and i18n usage (dashboard.series.* keys).
 *
 * Conventions (mirrors VolumeCard / DemoProjectCards tests):
 *   - The centralized setupTests.ts mock returns i18n KEY STRINGS verbatim, so
 *     assertions check for the key (e.g. "dashboard.series.novel_count") rather
 *     than a translated value.
 *   - The card itself is the interactive element (data-testid="series-card"),
 *     so the click test targets it directly.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SeriesCard } from "@/components/dashboard/SeriesCard";
import type { SeriesSummary } from "@/types";

const seriesFixture: SeriesSummary = {
  id: "series-1",
  title: "The Expanse",
  subtitle: "A sci-fi epic",
  status: "active",
  novel_count: 4,
};

describe("SeriesCard", () => {
  it("renders the series title and novel count", () => {
    render(<SeriesCard series={seriesFixture} onClick={vi.fn()} />);
    expect(screen.getByText("The Expanse")).toBeDefined();
    expect(screen.getByText("dashboard.series.novel_count")).toBeDefined();
  });

  it("renders the subtitle when present", () => {
    render(<SeriesCard series={seriesFixture} onClick={vi.fn()} />);
    expect(screen.getByText("A sci-fi epic")).toBeDefined();
  });

  it("omits the subtitle when absent", () => {
    const standalone: SeriesSummary = { ...seriesFixture, subtitle: null };
    render(<SeriesCard series={standalone} onClick={vi.fn()} />);
    expect(screen.queryByText("A sci-fi epic")).toBeNull();
  });

  it("renders the status badge via the status i18n key", () => {
    render(<SeriesCard series={seriesFixture} onClick={vi.fn()} />);
    expect(screen.getByText("dashboard.series.status.active")).toBeDefined();
  });

  it("calls onClick with the series id when the card is clicked", () => {
    const onClick = vi.fn();
    render(<SeriesCard series={seriesFixture} onClick={onClick} />);
    fireEvent.click(screen.getByTestId("series-card"));
    expect(onClick).toHaveBeenCalledWith("series-1");
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("uses the dashboard.series i18n keys (badge, novel count, status)", () => {
    render(<SeriesCard series={seriesFixture} onClick={vi.fn()} />);
    expect(screen.getByText("dashboard.series.badge")).toBeDefined();
    expect(screen.getByText("dashboard.series.novel_count")).toBeDefined();
    expect(screen.getByText("dashboard.series.status.active")).toBeDefined();
  });
});
