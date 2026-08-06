/**
 * SeriesDriftPanel component tests (Spec 4 Task 4).
 *
 * The panel is the orchestration layer for the Cross-Novel Drift section: it
 * lists novels for the band dropdown, fires BOTH checks (consistency + voice
 * drift) on the single "Check consistency" click, and delegates rendering to
 * `SeriesConflictList` + `SeriesDriftSummary`. These tests isolate the panel by
 * mocking the three hooks and the two pure child components.
 *
 * Conventions (mirrors SeriesVoicePanel.test.tsx): the centralized setupTests.ts
 * mock returns i18n KEY STRINGS verbatim, so assertions check for keys.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// --- Per-file mutable mock state (hoisted) -----------------------------------
const mock = vi.hoisted(() => ({
  novels: [] as { id: string; title: string }[],
  novelsLoading: false,
  consistency: {
    data: undefined as unknown,
    isPending: false,
    isError: false,
    mutate: vi.fn(),
    reset: vi.fn(),
  },
  drift: {
    data: undefined as unknown,
    isPending: false,
    isError: false,
    mutate: vi.fn(),
    reset: vi.fn(),
  },
}));

vi.mock("@/lib/hooks/useSeriesNovels", () => ({
  useSeriesNovels: () => ({ data: mock.novels, isLoading: mock.novelsLoading }),
}));

vi.mock("@/lib/hooks/useSeriesDrift", () => ({
  useSeriesConsistency: () => mock.consistency,
  useSeriesVoiceDrift: () => mock.drift,
}));

// Stub the pure child components so the panel test stays focused on orchestration.
vi.mock("@/components/series/SeriesConflictList", () => ({
  SeriesConflictList: ({ conflicts, summary }: { conflicts: unknown; summary?: string }) => (
    <div
      data-testid="series-conflict-list-stub"
      data-conflicts={JSON.stringify(conflicts)}
      data-summary={summary ?? ""}
    />
  ),
}));
vi.mock("@/components/series/SeriesDriftSummary", () => ({
  SeriesDriftSummary: ({ response }: { response: unknown }) => (
    <div data-testid="series-drift-summary-stub" data-response={JSON.stringify(response)} />
  ),
}));

import { SeriesDriftPanel } from "@/components/series/SeriesDriftPanel";

const SERIES_ID = "series-1";

const consistencyData = {
  series_id: SERIES_ID,
  novel_id: "novel-2",
  conflicts: [],
  summary: "All clear.",
  canon_entry_count: 3,
  chapter_count: 5,
};

const driftData = { novel_id: "novel-2", result: null, no_profile: null };

function resetMocks(): void {
  mock.novels = [
    { id: "novel-1", title: "Band I" },
    { id: "novel-2", title: "Band II" },
  ];
  mock.novelsLoading = false;
  mock.consistency = {
    data: undefined,
    isPending: false,
    isError: false,
    mutate: vi.fn(),
    reset: vi.fn(),
  };
  mock.drift = {
    data: undefined,
    isPending: false,
    isError: false,
    mutate: vi.fn(),
    reset: vi.fn(),
  };
}

describe("SeriesDriftPanel", () => {
  beforeEach(() => resetMocks());

  it("renders the title and an idle hint before any check", () => {
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);
    expect(screen.getByTestId("series-drift-panel")).toBeDefined();
    expect(screen.getByTestId("series-drift-idle").textContent).toContain(
      "series.drift.description",
    );
    expect(screen.queryByTestId("series-drift-consistency-section")).toBeNull();
  });

  it("lists the series novels in the band dropdown", () => {
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);
    const select = screen.getByTestId("series-drift-band-select") as HTMLSelectElement;
    const options = Array.from(select.options).map((o) => o.value);
    expect(options).toEqual(["", "novel-1", "novel-2"]);
  });

  it("disables the check button until a band is selected", () => {
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);
    const trigger = screen.getByTestId("series-drift-check") as HTMLButtonElement;
    expect(trigger.disabled).toBe(true);
  });

  it("fires both checks and resets stale state when the check button is clicked", async () => {
    const user = userEvent.setup();
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);

    await user.selectOptions(screen.getByTestId("series-drift-band-select"), "novel-2");
    await user.click(screen.getByTestId("series-drift-check"));

    expect(mock.consistency.reset).toHaveBeenCalledTimes(1);
    expect(mock.drift.reset).toHaveBeenCalledTimes(1);
    expect(mock.consistency.mutate).toHaveBeenCalledWith("novel-2");
    expect(mock.drift.mutate).toHaveBeenCalledWith("novel-2");
  });

  it("renders both result sections once a check has produced data", () => {
    mock.consistency.data = consistencyData;
    mock.drift.data = driftData;
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);

    expect(screen.getByTestId("series-drift-consistency-section")).toBeDefined();
    expect(screen.getByTestId("series-drift-voice-section")).toBeDefined();
    // Consistency child receives the conflicts + summary.
    const conflictStub = screen.getByTestId("series-conflict-list-stub");
    expect(conflictStub.getAttribute("data-summary")).toBe("All clear.");
    // Drift child receives the response verbatim.
    const driftStub = screen.getByTestId("series-drift-summary-stub");
    expect(JSON.parse(driftStub.getAttribute("data-response") ?? "null")).toEqual(driftData);
  });

  it("shows a per-section loading state while a check is pending", () => {
    mock.consistency.data = consistencyData; // already resolved
    mock.drift.isPending = true; // still running
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);

    expect(screen.queryByTestId("series-drift-consistency-section-loading")).toBeNull();
    expect(screen.getByTestId("series-drift-voice-section-loading").textContent).toContain(
      "series.drift.loading",
    );
  });

  it("shows a per-section error state when a check fails", () => {
    mock.consistency.isError = true;
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);

    expect(screen.getByTestId("series-drift-consistency-section-error").textContent).toContain(
      "series.drift.error",
    );
  });

  it("does not fire a check when no band is selected", async () => {
    const user = userEvent.setup();
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);
    // Button is disabled — clicking the disabled control is a no-op.
    await user.click(screen.getByTestId("series-drift-check"));
    expect(mock.consistency.mutate).not.toHaveBeenCalled();
  });
});
