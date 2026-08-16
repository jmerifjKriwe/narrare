/**
 * SeriesContextPreview component tests (C1 — honesty preview display).
 *
 * Pure presentational: renders the entry's band classification + token
 * estimate and the budget metadata. Conventions mirror
 * SeriesContextWindowField.test.tsx: the centralized setupTests mock
 * returns i18n KEY STRINGS verbatim, so assertions check for keys.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SeriesContextPreview } from "@/components/series/SeriesContextPreview";
import type { SeriesHistoryPreviewEntry, SeriesHistoryPreviewResponse } from "@/types";

const entry: SeriesHistoryPreviewEntry = {
  window_size: 3,
  token_budget: 16_000,
  estimated_tokens: 440,
  bands_total: 5,
  bands_full: 3,
  bands_short: 2,
  bands_truncated: 0,
  bands_dropped: 0,
  bands_missing: 0,
  budget_clipped: false,
};

const meta: SeriesHistoryPreviewResponse = {
  series_id: "series-1",
  current_window_size: 3,
  effective_series_history_budget: 16_000,
  effective_context_total: 32_000,
  effective_tier_base: 16_000,
  model_context_window: 128_000,
  budget_source: "cascade:uncapped",
  previews: [],
};

describe("SeriesContextPreview", () => {
  it("renders the bands + tokens line for the entry's window", () => {
    render(<SeriesContextPreview entry={entry} meta={meta} />);
    expect(screen.getByTestId("series-context-preview").getAttribute("data-window")).toBe("3");
    expect(screen.getByTestId("series-context-preview-line").textContent).toContain(
      "series.settings.contextPreview.bandsLine",
    );
    expect(screen.getByTestId("series-context-preview-line").textContent).toContain(
      "series.settings.contextPreview.tokenLine",
    );
  });

  it("always renders the budget line (tier-base semantics)", () => {
    render(<SeriesContextPreview entry={entry} meta={meta} />);
    expect(screen.getByTestId("series-context-preview-budget")).toBeDefined();
  });

  it("hides conditional notes when counts are zero and not clipped", () => {
    render(<SeriesContextPreview entry={entry} meta={meta} />);
    expect(screen.queryByTestId("series-context-preview-truncated")).toBeNull();
    expect(screen.queryByTestId("series-context-preview-dropped")).toBeNull();
    expect(screen.queryByTestId("series-context-preview-missing")).toBeNull();
    expect(screen.queryByTestId("series-context-preview-clipped")).toBeNull();
    expect(screen.queryByTestId("series-context-preview-window-unknown")).toBeNull();
  });

  it("shows truncation/drop/missing/clipped notes when present", () => {
    const clipped: SeriesHistoryPreviewEntry = {
      ...entry,
      bands_truncated: 1,
      bands_dropped: 2,
      bands_missing: 1,
      budget_clipped: true,
    };
    render(<SeriesContextPreview entry={clipped} meta={meta} />);
    expect(screen.getByTestId("series-context-preview-truncated")).toBeDefined();
    expect(screen.getByTestId("series-context-preview-dropped")).toBeDefined();
    expect(screen.getByTestId("series-context-preview-missing")).toBeDefined();
    expect(screen.getByTestId("series-context-preview-clipped")).toBeDefined();
  });

  it("shows the window-unknown note only when the model window is null", () => {
    const unknown: SeriesHistoryPreviewResponse = { ...meta, model_context_window: null };
    render(<SeriesContextPreview entry={entry} meta={unknown} />);
    expect(screen.getByTestId("series-context-preview-window-unknown")).toBeDefined();
  });
});
