/**
 * BandSummaryCard component tests (Spec 2, Task 8).
 *
 * The card shows the auto-generated band summary for one novel, with controls
 * to regenerate, set a manual override, and clear it. These tests isolate the
 * card by mocking the four `useBandSummary*` hooks (each has its own suite).
 *
 * Conventions (mirrors SeriesSettings.test.tsx + BaendeList.test.tsx): the
 * centralized setupTests.ts mock returns i18n KEY STRINGS verbatim, so
 * assertions check for keys.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { BandSummary } from "@/types";

// --- Per-file mutable mock state (hoisted) -----------------------------------
const mock = vi.hoisted(() => ({
  query: {
    data: undefined as BandSummary | undefined,
    isLoading: false,
    isError: false,
  },
  generate: vi.fn(),
  generatePending: false,
  updateOverride: vi.fn(),
  updateOverridePending: false,
  clearOverride: vi.fn(),
  clearOverridePending: false,
}));

vi.mock("@/lib/hooks/useBandSummary", () => ({
  useBandSummary: () => mock.query,
  useGenerateBandSummary: () => ({
    mutate: (...args: unknown[]) => mock.generate(...args),
    isPending: mock.generatePending,
  }),
  useUpdateBandSummaryOverride: () => ({
    mutate: (...args: unknown[]) => mock.updateOverride(...args),
    isPending: mock.updateOverridePending,
  }),
  useClearBandSummaryOverride: () => ({
    mutate: (...args: unknown[]) => mock.clearOverride(...args),
    isPending: mock.clearOverridePending,
  }),
}));

import { BandSummaryCard } from "@/components/series/BandSummaryCard";

const SERIES_ID = "series-1";
const NOVEL_ID = "novel-1";

const baseSummary: BandSummary = {
  novel_id: NOVEL_ID,
  full_summary: "The crew of the Rocinante discovers…",
  short_summary: "Discovery.",
  override: null,
  generated_at: "2026-08-02T12:00:00Z",
};

function resetMocks(): void {
  mock.query = { data: baseSummary, isLoading: false, isError: false };
  mock.generate = vi.fn();
  mock.updateOverride = vi.fn();
  mock.clearOverride = vi.fn();
  mock.generatePending = false;
  mock.updateOverridePending = false;
  mock.clearOverridePending = false;
}

describe("BandSummaryCard", () => {
  beforeEach(() => {
    resetMocks();
  });

  it("shows a loading state while the summary is fetching", () => {
    mock.query = { data: undefined, isLoading: true, isError: false };
    render(<BandSummaryCard seriesId={SERIES_ID} novelId={NOVEL_ID} />);
    expect(screen.getByTestId("band-summary-loading")).toBeDefined();
  });

  it("shows an empty/CTA state when no summary exists", () => {
    mock.query = { data: undefined, isLoading: false, isError: true };
    render(<BandSummaryCard seriesId={SERIES_ID} novelId={NOVEL_ID} />);
    expect(screen.getByTestId("band-summary-empty")).toBeDefined();
  });

  it("renders the full summary and generated-at timestamp", () => {
    render(<BandSummaryCard seriesId={SERIES_ID} novelId={NOVEL_ID} />);
    expect(screen.getByTestId("band-summary-full").textContent).toContain(
      "The crew of the Rocinante discovers",
    );
    expect(screen.getByTestId("band-summary-generated-at")).toBeDefined();
  });

  it("shows the override-active badge when an override is set", () => {
    mock.query = {
      data: { ...baseSummary, override: "Manual edit" },
      isLoading: false,
      isError: false,
    };
    render(<BandSummaryCard seriesId={SERIES_ID} novelId={NOVEL_ID} />);
    expect(screen.getByTestId("band-summary-override-active")).toBeDefined();
  });

  it("triggers generate when the regenerate button is clicked", async () => {
    const user = userEvent.setup();
    render(<BandSummaryCard seriesId={SERIES_ID} novelId={NOVEL_ID} />);
    await user.click(screen.getByTestId("band-summary-regenerate"));
    expect(mock.generate).toHaveBeenCalled();
  });

  it("triggers generate from the empty state CTA", async () => {
    mock.query = { data: undefined, isLoading: false, isError: true };
    const user = userEvent.setup();
    render(<BandSummaryCard seriesId={SERIES_ID} novelId={NOVEL_ID} />);
    await user.click(screen.getByTestId("band-summary-generate-cta"));
    expect(mock.generate).toHaveBeenCalled();
  });

  it("saves an override via PATCH when the save button is clicked", async () => {
    const user = userEvent.setup();
    render(<BandSummaryCard seriesId={SERIES_ID} novelId={NOVEL_ID} />);

    const textarea = screen.getByTestId("band-summary-override-input") as HTMLTextAreaElement;
    await user.clear(textarea);
    await user.type(textarea, "My manual summary");

    await user.click(screen.getByTestId("band-summary-save-override"));
    // mutate(override, options) — check the first arg only (mirrors
    // SeriesSettings.test.tsx pattern).
    expect(mock.updateOverride).toHaveBeenCalled();
    expect(mock.updateOverride.mock.calls[0][0]).toBe("My manual summary");
  });

  it("clears the override via DELETE when the clear button is clicked", async () => {
    mock.query = {
      data: { ...baseSummary, override: "Manual edit" },
      isLoading: false,
      isError: false,
    };
    const user = userEvent.setup();
    render(<BandSummaryCard seriesId={SERIES_ID} novelId={NOVEL_ID} />);
    await user.click(screen.getByTestId("band-summary-clear-override"));
    expect(mock.clearOverride).toHaveBeenCalled();
  });
});
