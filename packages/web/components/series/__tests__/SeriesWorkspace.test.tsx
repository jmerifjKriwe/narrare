/**
 * SeriesWorkspace component tests (Spec 1, Slice 4, Task 4.6).
 *
 * The workspace is the persistent shell for /series/[id]/* routes: a series
 * hero header, a 4-tab navigation bar (segment-based routing), and a tab
 * content area that crossfades between routes. It fetches the Series via the
 * `useSeries` hook and renders the matched route page as `children`.
 *
 * Conventions (mirrors SeriesCard.test.tsx):
 *   - The centralized setupTests.ts mock returns i18n KEY STRINGS verbatim, so
 *     assertions check for the key (e.g. "series.workspace.tabs.baende").
 *   - `@/lib/hooks/useSeries` and `next/navigation` are mocked per-file so each
 *     test can control the resolved Series and the active route.
 *   - motion/react is neutralized globally (setupTests.ts), so PhaseCrossfade
 *     mounts its children immediately — content is always present.
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Series } from "@/types";

// --- Per-file mutable mock state (hoisted so vi.mock factories can close over it) ---
const mock = vi.hoisted(() => ({
  pathname: "/series/series-1",
  // Shape matches the fields SeriesWorkspace destructures from useSeries().
  result: {
    data: undefined as Series | undefined,
    isLoading: false,
    isError: false,
    error: null as unknown,
  },
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mock.pathname,
}));

vi.mock("@/lib/hooks/useSeries", () => ({
  useSeries: () => mock.result,
}));

// Static import is safe: vitest applies the hoisted mocks before this module's
// dependency graph is evaluated.
import { SeriesWorkspace } from "@/components/series/SeriesWorkspace";

const seriesFixture: Series = {
  id: "series-1",
  user_id: "user-1",
  title: "The Expanse",
  subtitle: "A sci-fi epic",
  description: null,
  genre: "sci-fi",
  writing_language: "en",
  status: "active",
  planned_novel_count: 9,
  novel_count: 4,
};

function resetResult(): void {
  mock.result = {
    data: seriesFixture,
    isLoading: false,
    isError: false,
    error: null,
  };
}

describe("SeriesWorkspace", () => {
  beforeEach(() => {
    mock.pathname = "/series/series-1";
    resetResult();
  });

  it("renders the series title in the hero header", () => {
    render(
      <SeriesWorkspace seriesId="series-1">
        <div />
      </SeriesWorkspace>,
    );
    expect(screen.getByText("The Expanse")).toBeDefined();
  });

  it("renders the series badge and status label", () => {
    render(
      <SeriesWorkspace seriesId="series-1">
        <div />
      </SeriesWorkspace>,
    );
    expect(screen.getByText("series.workspace.badgeSeries")).toBeDefined();
    expect(screen.getByText("series.workspace.status.active")).toBeDefined();
  });

  it("renders four tabs with translated labels", () => {
    render(
      <SeriesWorkspace seriesId="series-1">
        <div />
      </SeriesWorkspace>,
    );
    expect(screen.getByRole("tab", { name: /series\.workspace\.tabs\.baende/ })).toBeDefined();
    expect(screen.getByRole("tab", { name: /series\.workspace\.tabs\.canon/ })).toBeDefined();
    expect(screen.getByRole("tab", { name: /series\.workspace\.tabs\.settings/ })).toBeDefined();
    expect(screen.getByRole("tab", { name: /series\.workspace\.tabs\.voice/ })).toBeDefined();
  });

  it("marks the Bände tab active on the base route", () => {
    mock.pathname = "/series/series-1";
    render(
      <SeriesWorkspace seriesId="series-1">
        <div />
      </SeriesWorkspace>,
    );
    const baende = screen.getByRole("tab", { name: /series\.workspace\.tabs\.baende/ });
    const canon = screen.getByRole("tab", { name: /series\.workspace\.tabs\.canon/ });
    expect(baende.getAttribute("aria-selected")).toBe("true");
    expect(canon.getAttribute("aria-selected")).toBe("false");
  });

  it("marks the Canon tab active on the canon route and Bände inactive", () => {
    mock.pathname = "/series/series-1/canon";
    render(
      <SeriesWorkspace seriesId="series-1">
        <div />
      </SeriesWorkspace>,
    );
    const canon = screen.getByRole("tab", { name: /series\.workspace\.tabs\.canon/ });
    const baende = screen.getByRole("tab", { name: /series\.workspace\.tabs\.baende/ });
    expect(canon.getAttribute("aria-selected")).toBe("true");
    expect(baende.getAttribute("aria-selected")).toBe("false");
  });

  it("renders children inside the tab content area", () => {
    render(
      <SeriesWorkspace seriesId="series-1">
        <div data-testid="tab-content">Bände list goes here</div>
      </SeriesWorkspace>,
    );
    expect(screen.getByTestId("tab-content")).toBeDefined();
  });

  it("renders the Voice tab as disabled and non-navigable", () => {
    render(
      <SeriesWorkspace seriesId="series-1">
        <div />
      </SeriesWorkspace>,
    );
    const voice = screen.getByRole("tab", { name: /series\.workspace\.tabs\.voice/ });
    expect(voice.getAttribute("aria-disabled")).toBe("true");
    // A disabled tab must not be an anchor (no route navigation).
    expect(voice.tagName).not.toBe("A");
    expect(voice.getAttribute("href")).toBeNull();
    // Shows the "coming in Spec 3" hint.
    expect(screen.getByText(/series\.workspace\.comingInSpec3/)).toBeDefined();
  });

  it("shows a loading state while the series is loading", () => {
    mock.result = { data: undefined, isLoading: true, isError: false, error: null };
    render(
      <SeriesWorkspace seriesId="series-1">
        <div data-testid="tab-content" />
      </SeriesWorkspace>,
    );
    expect(screen.getByText("series.workspace.loading")).toBeDefined();
    expect(screen.queryByTestId("tab-content")).toBeNull();
  });

  it("shows a not-found state when the series fails to load", () => {
    mock.result = { data: undefined, isLoading: false, isError: true, error: new Error("boom") };
    render(
      <SeriesWorkspace seriesId="series-1">
        <div data-testid="tab-content" />
      </SeriesWorkspace>,
    );
    expect(screen.getByText("series.workspace.notFound")).toBeDefined();
    expect(screen.queryByTestId("tab-content")).toBeNull();
  });
});
