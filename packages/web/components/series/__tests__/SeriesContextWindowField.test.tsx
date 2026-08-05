/**
 * SeriesContextWindowField component tests (Spec 2, context_window setting).
 *
 * The field reads the Series settings (GET /series/{id}/settings), shows the
 * current context_window_size in a number input, and saves changes via PATCH
 * /series/{id}/settings. It lives on the Settings tab alongside the metadata
 * form but is a separate component because it persists to a distinct endpoint.
 *
 * Conventions mirror SeriesSettings.test.tsx: the centralized setupTests mock
 * returns i18n KEY STRINGS verbatim, so assertions check for keys.
 * `@/lib/hooks/useSeries` (useSeriesSettings + useUpdateSeriesSettings) is
 * mocked per-file so each test controls the resolved settings + mutation.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SeriesSettings, SeriesSettingsUpdate } from "@/types";

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
}));

vi.mock("@/lib/hooks/useSeries", () => ({
  useSeriesSettings: () => mock.result,
  useUpdateSeriesSettings: () => ({
    mutate: (...args: unknown[]) => mock.update(...args),
    isPending: mock.updatePending,
    isError: mock.updateError,
  }),
}));

import { SeriesContextWindowField } from "@/components/series/SeriesContextWindowField";

const settingsDefault: SeriesSettings = {
  series_id: "series-1",
  author_voice: null,
  context_window_size: 3,
};

function resetResult(): void {
  mock.result = { data: settingsDefault, isLoading: false, isError: false, error: null };
  mock.update = vi.fn();
  mock.updatePending = false;
  mock.updateError = false;
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

  it("populates the input with the current context_window_size", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect((screen.getByTestId("series-context-window-input") as HTMLInputElement).value).toBe("3");
  });

  it("does not show the Save button until the value is changed", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.queryByTestId("series-context-window-save")).toBeNull();
  });

  it("calls updateSettings with the new value when Save is clicked", async () => {
    const user = userEvent.setup();
    render(<SeriesContextWindowField seriesId="series-1" />);

    const input = screen.getByTestId("series-context-window-input") as HTMLInputElement;
    await user.clear(input);
    await user.type(input, "7");

    const saveBtn = await waitFor(() => screen.getByTestId("series-context-window-save"));
    await user.click(saveBtn);

    expect(mock.update).toHaveBeenCalled();
    const expected: SeriesSettingsUpdate = { context_window_size: 7 };
    expect(mock.update.mock.calls[0][0]).toEqual(expected);
  });

  it("enforces the min bound of 1 on the input", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);
    const input = screen.getByTestId("series-context-window-input") as HTMLInputElement;
    expect(input.min).toBe("1");
  });

  it("enforces the max bound of 50 on the input", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);
    const input = screen.getByTestId("series-context-window-input") as HTMLInputElement;
    expect(input.max).toBe("50");
  });

  it("renders the help text describing what the window controls", () => {
    render(<SeriesContextWindowField seriesId="series-1" />);
    expect(screen.getByText("series.settings.contextWindow.help")).toBeDefined();
  });
});
