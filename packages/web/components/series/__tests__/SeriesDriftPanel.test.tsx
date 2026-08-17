/**
 * SeriesDriftPanel component tests (Spec 4 Task 4 + C2 snapshot hydration).
 *
 * The panel is the orchestration layer for the Cross-Novel Drift section: it
 * lists novels for the band dropdown, fires BOTH checks (consistency + voice
 * drift) on the single "Check consistency" click, and delegates rendering to
 * `SeriesConflictList` + `SeriesDriftSummary`. These tests isolate the panel by
 * mocking the four hooks and the two pure child components.
 *
 * Conventions (mirrors SeriesVoicePanel.test.tsx): the centralized setupTests.ts
 * mock returns i18n KEY STRINGS verbatim, so assertions check for keys.
 *
 * C2 (Task 9): the panel hydrates from the persisted snapshot before any run,
 * badges it stale, prefers fresh run data, and resets fresh results on band
 * change. The typed-ICU-arg carry-forward from the Task 8 review (date arg in
 * series.drift.snapshot.restored) is covered by the real-next-intl describe at
 * the bottom of this file (mirrors SeriesContextWindowField.test.tsx).
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
  snapshot: {
    data: undefined as
      | {
          stale: boolean;
          generated_at: string | null;
          consistency?: unknown;
          voice_drift?: unknown;
        }
      | undefined,
  },
}));

vi.mock("@/lib/hooks/useSeriesNovels", () => ({
  useSeriesNovels: () => ({ data: mock.novels, isLoading: mock.novelsLoading }),
}));

vi.mock("@/lib/hooks/useSeriesDrift", () => ({
  useSeriesConsistency: () => mock.consistency,
  useSeriesVoiceDrift: () => mock.drift,
  useSeriesDriftSnapshot: () => ({ data: mock.snapshot.data }),
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
import deStudio from "../../../../i18n/messages/de/studio.json";
import enStudio from "../../../../i18n/messages/en/studio.json";
import frStudio from "../../../../i18n/messages/fr/studio.json";

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
  mock.snapshot = { data: undefined };
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

    // C2: reset fires twice — once when the band is selected (handleSelect
    // clears the previous band's results) and once when the check starts
    // (handleCheck clears the persisted display while the fresh checks run).
    expect(mock.consistency.reset).toHaveBeenCalledTimes(2);
    expect(mock.drift.reset).toHaveBeenCalledTimes(2);
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

  it("renders the persisted snapshot sections before any run (C2)", async () => {
    mock.snapshot = {
      data: {
        stale: false,
        generated_at: "2026-08-16T12:00:00.000Z",
        consistency: consistencyData,
        voice_drift: driftData,
      },
    };

    const user = userEvent.setup();
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);
    await user.selectOptions(screen.getByTestId("series-drift-band-select"), "novel-2");

    expect(screen.getByTestId("series-drift-consistency-section")).toBeDefined();
    expect(screen.getByTestId("series-drift-summary-stub")).toBeDefined();
    expect(screen.getByTestId("series-drift-snapshot-hint").textContent).toContain(
      "series.drift.snapshot.restored",
    );
  });

  it("shows the stale warning when the snapshot is stale", async () => {
    mock.snapshot = {
      data: {
        stale: true,
        generated_at: "2026-08-16T12:00:00.000Z",
        consistency: consistencyData,
        voice_drift: driftData,
      },
    };

    const user = userEvent.setup();
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);
    await user.selectOptions(screen.getByTestId("series-drift-band-select"), "novel-2");

    expect(screen.getByTestId("series-drift-snapshot-hint").textContent).toContain(
      "series.drift.snapshot.stale",
    );
  });

  it("prefers fresh run data over the persisted snapshot", async () => {
    mock.snapshot = {
      data: {
        stale: true,
        generated_at: "2026-08-16T12:00:00.000Z",
        consistency: consistencyData,
        voice_drift: driftData,
      },
    };
    mock.consistency = {
      data: { ...consistencyData, summary: "Fresh run." },
      isPending: false,
      isError: false,
      mutate: vi.fn(),
      reset: vi.fn(),
    };

    const user = userEvent.setup();
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);
    await user.selectOptions(screen.getByTestId("series-drift-band-select"), "novel-2");

    // Fresh run summary wins over the snapshot's "All clear."
    expect((screen.getByTestId("series-conflict-list-stub") as HTMLElement).dataset.summary).toBe(
      "Fresh run.",
    );
    // And the snapshot hint is hidden (fresh data is the visible source).
    expect(screen.queryByTestId("series-drift-snapshot-hint")).toBeNull();
  });

  it("resets fresh results when the band selection changes", async () => {
    mock.consistency = {
      data: consistencyData,
      isPending: false,
      isError: false,
      mutate: vi.fn(),
      reset: vi.fn(),
    };
    const user = userEvent.setup();
    render(<SeriesDriftPanel seriesId={SERIES_ID} />);
    await user.selectOptions(screen.getByTestId("series-drift-band-select"), "novel-2");

    await user.selectOptions(screen.getByTestId("series-drift-band-select"), "novel-1");

    expect(mock.consistency.reset).toHaveBeenCalled();
  });
});

describe("series.drift.snapshot.restored — ICU arg contract via real next-intl (carry-forward)", () => {
  // Binding carry from the Task 8 review: the i18n validator's regex is blind
  // to typed ICU args, and the centralized setupTests mock returns the KEY
  // verbatim, so neither can detect arg drift between the panel's t() call
  // and the catalogs. Here the component's EXACT call shape ({ generatedAt }
  // as a Date — Intl.DateTimeFormat needs Date-coercible input; Task 7 types
  // generated_at as an ISO string, hence the new Date(...) in the panel) runs
  // through REAL next-intl (vi.importActual bypasses the global mock):
  //  - a catalog using a different arg name, or the component drifting,
  //    produces FORMATTING_ERROR → next-intl returns the bare key → the
  //    not.toBe assertion fails;
  //  - a literal "{generatedAt, date, medium}" leak or a failed Date
  //    coercion ("Invalid Date") also fails the negative assertions.
  it.each([
    ["en", enStudio],
    ["de", deStudio],
    ["fr", frStudio],
  ])("%s catalog formats {generatedAt, date, medium} with the component's exact args", async (locale, studio) => {
    const { createTranslator } = await vi.importActual<typeof import("next-intl")>("next-intl");
    const t = createTranslator({ locale, messages: { studio }, namespace: "studio" });

    // Exact call the panel makes for the snapshot hint (see
    // SeriesDriftPanel's restored branch; the 12:00Z instant keeps the date
    // year stable in any realistic test timezone).
    const out = t("series.drift.snapshot.restored", {
      generatedAt: new Date("2026-08-16T12:00:00.000Z"),
    });

    expect(out).toContain("2026"); // the date was formatted, not dropped
    expect(out).not.toContain("{"); // no literal "{generatedAt, date, medium}" in the output
    expect(out).not.toContain("Invalid Date"); // no failed Date coercion
    expect(out).not.toBe("series.drift.snapshot.restored"); // no FORMATTING_ERROR fallback
  });
});
