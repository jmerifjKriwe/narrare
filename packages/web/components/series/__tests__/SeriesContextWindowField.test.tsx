/**
 * SeriesContextWindowField component tests (C1 — slider + live preview).
 *
 * The field renders a 1-10 slider (design §4.1) bound to the saved
 * context_window_size, a live honesty preview from
 * useSeriesHistoryPreview, and saves via PATCH /series/{id}/settings.
 * Conventions: the centralized setupTests mock returns i18n KEY STRINGS
 * verbatim, so assertions check for keys; hooks mocked per-file.
 *
 * Beyond the brief's 10 behaviour tests, this file carries forward the two
 * Task 7a review findings (binding):
 *  - ICU arg-name contract: the savedOutOfRange key is rendered through REAL
 *    next-intl (vi.importActual + createTranslator) with the component's
 *    exact call shape — the key-mock cannot detect arg drift (a missing or
 *    renamed arg makes next-intl emit FORMATTING_ERROR and fall back to the
 *    bare key, which contains no formatted numbers).
 *  - axe pass on the composite component (runAxe from @/lib/test/axe; the
 *    toHaveNoViolations matcher is registered globally in setupTests).
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SeriesContextWindowField } from "@/components/series/SeriesContextWindowField";
import { runAxe } from "@/lib/test/axe";
import type { SeriesHistoryPreviewResponse, SeriesSettings } from "@/types";
import deStudio from "../../../../i18n/messages/de/studio.json";
import enStudio from "../../../../i18n/messages/en/studio.json";
import frStudio from "../../../../i18n/messages/fr/studio.json";

// --- Per-file mutable mock state (hoisted) -----------------------------------
const mock = vi.hoisted(() => ({
  result: {
    data: undefined as SeriesSettings | undefined,
    isLoading: false,
    isError: false,
    error: null as unknown,
  },
  update: vi.fn(),
  updatePending: false,
  updateError: false,
  preview: {
    data: undefined as SeriesHistoryPreviewResponse | undefined,
    isLoading: false,
    isError: false,
    error: null as unknown,
  },
}));

vi.mock("@/lib/hooks/useSeries", () => ({
  useSeriesSettings: () => mock.result,
  useUpdateSeriesSettings: () => ({
    mutate: (...args: unknown[]) => mock.update(...args),
    isPending: mock.updatePending,
    isError: mock.updateError,
  }),
  useSeriesHistoryPreview: () => mock.preview,
}));

const settingsDefault: SeriesSettings = {
  series_id: "series-1",
  author_voice: null,
  context_window_size: 3,
};

function makePreview(current: number): SeriesHistoryPreviewResponse {
  const top = Math.max(10, current);
  return {
    series_id: "series-1",
    current_window_size: current,
    effective_series_history_budget: 16_000,
    effective_context_total: 32_000,
    effective_tier_base: 16_000,
    model_context_window: 128_000,
    budget_source: "cascade:uncapped",
    previews: Array.from({ length: top }, (_, i) => ({
      window_size: i + 1,
      token_budget: 16_000,
      estimated_tokens: 100 * (i + 1),
      bands_total: 5,
      bands_full: Math.min(i + 1, 5),
      bands_short: Math.max(5 - (i + 1), 0),
      bands_truncated: 0,
      bands_dropped: 0,
      bands_missing: 0,
      budget_clipped: i + 1 >= 5,
    })),
  };
}

function resetResult(): void {
  mock.result = { data: settingsDefault, isLoading: false, isError: false, error: null };
  mock.update = vi.fn();
  mock.updatePending = false;
  mock.updateError = false;
  mock.preview = { data: makePreview(3), isLoading: false, isError: false, error: null };
}

describe("SeriesContextWindowField", () => {
  beforeEach(() => {
    resetResult();
  });

  it("shows a loading state while settings are loading", () => {
    mock.result = { data: undefined, isLoading: true, isError: false, error: null };
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByTestId("series-context-window-loading")).toBeDefined();
  });

  it("shows an error state when settings fail to load", () => {
    mock.result = { data: undefined, isLoading: false, isError: true, error: new Error("x") };
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByTestId("series-context-window-error")).toBeDefined();
  });

  it("renders a range slider bounded 1-10 with the saved value", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);
    const slider = screen.getByTestId("series-context-window-slider") as HTMLInputElement;
    expect(slider.type).toBe("range");
    expect(slider.min).toBe("1");
    expect(slider.max).toBe("10");
    expect(slider.value).toBe("3");
    expect(screen.getByTestId("series-context-window-value").textContent).toBe("3");
  });

  it("renders the live preview for the current window", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByTestId("series-context-preview").getAttribute("data-window")).toBe("3");
  });

  it("switches the preview when the slider moves (no refetch needed)", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);

    fireEvent.change(screen.getByTestId("series-context-window-slider"), {
      target: { value: "7" },
    });

    expect(screen.getByTestId("series-context-preview").getAttribute("data-window")).toBe("7");
    expect(screen.getByTestId("series-context-window-value").textContent).toBe("7");
    expect(mock.update).not.toHaveBeenCalled();
  });

  it("shows Save only after a change and PATCHes the slider value", async () => {
    const user = userEvent.setup();
    render(<SeriesContextWindowField seriesId="series-1" />);

    expect(screen.queryByTestId("series-context-window-save")).toBeNull();

    fireEvent.change(screen.getByTestId("series-context-window-slider"), {
      target: { value: "7" },
    });

    const saveBtn = await waitFor(() => screen.getByTestId("series-context-window-save"));
    await user.click(saveBtn);

    expect(mock.update).toHaveBeenCalled();
    expect(mock.update.mock.calls[0][0]).toEqual({ context_window_size: 7 });
  });

  it("collapses dirty without a request when slid back to the saved value", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);

    fireEvent.change(screen.getByTestId("series-context-window-slider"), {
      target: { value: "7" },
    });
    expect(screen.getByTestId("series-context-window-save")).toBeDefined();

    fireEvent.change(screen.getByTestId("series-context-window-slider"), {
      target: { value: "3" },
    });

    expect(screen.queryByTestId("series-context-window-save")).toBeNull();
    expect(mock.update).not.toHaveBeenCalled();
  });

  it("keeps the draft while the PATCH round-trip is in flight and clears dirty only after refetched settings confirm it", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<SeriesContextWindowField seriesId="series-1" />);

    fireEvent.change(screen.getByTestId("series-context-window-slider"), {
      target: { value: "7" },
    });
    await user.click(screen.getByTestId("series-context-window-save"));
    expect(mock.update).toHaveBeenCalledWith({ context_window_size: 7 });

    // PATCH in flight, settings refetch NOT landed (still 3): dirty must NOT
    // clear here — clearing early would run the re-sync effect against the
    // stale settings and flash the slider back to 3 (the draft-flicker bug
    // the confirmation effect exists to prevent).
    mock.updatePending = true;
    rerender(<SeriesContextWindowField seriesId="series-1" />);
    const slider = screen.getByTestId("series-context-window-slider") as HTMLInputElement;
    expect(slider.value).toBe("7");
    expect(screen.getByTestId("series-context-window-save")).toBeDefined();

    // Refetch lands: fresh settings confirm the draft → dirty clears, Save
    // collapses, and the slider STAYS at 7 (no flicker to the old value).
    mock.updatePending = false;
    mock.result = {
      data: { ...settingsDefault, context_window_size: 7 },
      isLoading: false,
      isError: false,
      error: null,
    };
    rerender(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.queryByTestId("series-context-window-save")).toBeNull();
    expect((screen.getByTestId("series-context-window-slider") as HTMLInputElement).value).toBe(
      "7",
    );
  });

  it("renders the help text describing what the window controls", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByText("series.settings.contextWindow.help")).toBeDefined();
  });

  it("shows a dedicated loading line while the preview loads (slider usable)", () => {
    mock.preview = { data: undefined, isLoading: true, isError: false, error: null };
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByTestId("series-context-preview-loading")).toBeDefined();
    expect(screen.getByTestId("series-context-window-slider")).toBeDefined();
  });

  it("shows a dedicated error line when the preview fails (slider usable)", () => {
    mock.preview = { data: undefined, isLoading: false, isError: true, error: new Error("x") };
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByTestId("series-context-preview-error")).toBeDefined();
    expect(screen.getByTestId("series-context-window-slider")).toBeDefined();
  });

  it("handles a saved value above the slider range honestly", () => {
    mock.result = {
      data: { ...settingsDefault, context_window_size: 12 },
      isLoading: false,
      isError: false,
      error: null,
    };
    mock.preview = { data: makePreview(12), isLoading: false, isError: false, error: null };

    render(<SeriesContextWindowField seriesId="series-1" />);

    expect(screen.getByTestId("series-context-window-out-of-range")).toBeDefined();
    expect(screen.getByTestId("series-context-window-value").textContent).toBe("12");
    // The extended server range covers the saved value's preview.
    expect(screen.getByTestId("series-context-preview").getAttribute("data-window")).toBe("12");
  });
});

describe("SeriesContextWindowField — axe (carry-forward from Task 7a review)", () => {
  beforeEach(() => {
    resetResult();
  });

  it("has no axe violations in the default interactive state (slider + preview)", async () => {
    const { container } = render(<SeriesContextWindowField seriesId="series-1" />);
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("has no axe violations with the out-of-range notice rendered", async () => {
    mock.result = {
      data: { ...settingsDefault, context_window_size: 12 },
      isLoading: false,
      isError: false,
      error: null,
    };
    mock.preview = { data: makePreview(12), isLoading: false, isError: false, error: null };

    const { container } = render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByTestId("series-context-window-out-of-range")).toBeDefined();
    expect(await runAxe(container)).toHaveNoViolations();
  });
});

describe("savedOutOfRange — ICU arg-name contract via real next-intl (carry-forward)", () => {
  // The centralized setupTests mock returns the KEY verbatim, so it cannot
  // detect arg drift between the component's t() call and the catalogs.
  // Here the component's EXACT call shape ({ value, max } on
  // series.settings.contextPreview.savedOutOfRange, namespace "studio") runs
  // through REAL next-intl (vi.importActual bypasses the global mock):
  //  - a catalog using a different arg name, or the component drifting,
  //    produces FORMATTING_ERROR → next-intl returns the bare key, which
  //    contains neither "12" nor "10" → the assertion fails;
  //  - a literal "{value, number}" leak or an unresolved number arg
  //    ("NaN") also fails the negative assertions.
  it.each([
    ["en", enStudio],
    ["de", deStudio],
    ["fr", frStudio],
  ])("%s catalog formats {value}/{max} with the component's exact args", async (locale, studio) => {
    const { createTranslator } = await vi.importActual<typeof import("next-intl")>("next-intl");
    const t = createTranslator({ locale, messages: { studio }, namespace: "studio" });

    // Exact call the component makes for saved=12, MAX_WINDOW=10 (see the
    // out-of-range notice in SeriesContextWindowField).
    const out = t("series.settings.contextPreview.savedOutOfRange", { value: 12, max: 10 });

    expect(out).toContain("12");
    expect(out).toContain("10");
    expect(out).not.toContain("{"); // no literal "{value, number}" in the output
    expect(out).not.toContain("NaN"); // no unresolved ICU number arg
    expect(out).not.toBe("series.settings.contextPreview.savedOutOfRange"); // no FORMATTING_ERROR fallback
  });
});
