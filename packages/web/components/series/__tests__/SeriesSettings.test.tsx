/**
 * SeriesSettings component tests (Spec 1, Slice 4, Task 4.7).
 *
 * The settings form edits Series metadata (title, subtitle, description, genre,
 * writing_language, status, planned_novel_count) via `useUpdateSeries`. The
 * status field is constrained to allowed transitions (draft→active→completed
 * adjacency). A disabled Voice subsection is a placeholder for Spec 3.
 *
 * Conventions (mirrors SeriesWorkspace.test.tsx + NovelDetailsTab pattern):
 * the centralized setupTests.ts mock returns i18n KEY STRINGS verbatim, so
 * assertions check for keys. `@/lib/hooks/useSeries` (useSeries +
 * useUpdateSeries) is mocked per-file so each test controls the resolved Series
 * and the update mutation.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Series, SeriesUpdate } from "@/types";

// --- Per-file mutable mock state (hoisted) -----------------------------------
const mock = vi.hoisted(() => ({
  result: {
    data: undefined as Series | undefined,
    isLoading: false,
    isError: false,
    error: null as unknown,
  },
  update: vi.fn(),
  updatePending: false,
  updateError: false,
}));

vi.mock("@/lib/hooks/useSeries", () => ({
  useSeries: () => mock.result,
  useUpdateSeries: () => ({
    mutate: (...args: unknown[]) => mock.update(...args),
    isPending: mock.updatePending,
    isError: mock.updateError,
  }),
}));

import { SeriesSettings } from "@/components/series/SeriesSettings";

const draftSeries: Series = {
  id: "series-1",
  user_id: "user-1",
  title: "The Expanse",
  subtitle: "A sci-fi epic",
  description: "Description here",
  genre: "sci-fi",
  writing_language: "en",
  status: "draft",
  planned_novel_count: 9,
  novel_count: 0,
};

function resetResult(): void {
  mock.result = { data: draftSeries, isLoading: false, isError: false, error: null };
  mock.update = vi.fn();
  mock.updatePending = false;
  mock.updateError = false;
}

describe("SeriesSettings", () => {
  beforeEach(() => {
    resetResult();
  });

  it("shows a loading state while the series is loading", () => {
    mock.result = { data: undefined, isLoading: true, isError: false, error: null };
    render(<SeriesSettings seriesId="series-1" />);
    expect(screen.getByTestId("series-settings-loading")).toBeDefined();
  });

  it("shows an error state when the series fails to load", () => {
    mock.result = { data: undefined, isLoading: false, isError: true, error: new Error("x") };
    render(<SeriesSettings seriesId="series-1" />);
    expect(screen.getByTestId("series-settings-error")).toBeDefined();
  });

  it("populates the title field from the series", () => {
    render(<SeriesSettings seriesId="series-1" />);
    expect((screen.getByTestId("series-settings-title") as HTMLInputElement).value).toBe(
      "The Expanse",
    );
  });

  it("limits the status select to allowed transitions from draft (draft, active)", () => {
    render(<SeriesSettings seriesId="series-1" />);
    const statusSelect = screen.getByTestId("series-settings-status") as HTMLSelectElement;
    const optionValues = Array.from(statusSelect.options).map((o) => o.value);
    expect(optionValues).toEqual(expect.arrayContaining(["draft", "active"]));
    expect(optionValues).not.toContain("completed");
  });

  it("does not show the Save button until a field is changed", () => {
    render(<SeriesSettings seriesId="series-1" />);
    expect(screen.queryByTestId("series-settings-save")).toBeNull();
  });

  it("calls update with the changed field when Save is clicked", async () => {
    const user = userEvent.setup();
    render(<SeriesSettings seriesId="series-1" />);

    const titleInput = screen.getByTestId("series-settings-title") as HTMLInputElement;
    await user.clear(titleInput);
    await user.type(titleInput, "The Expanse Saga");

    const saveBtn = await waitFor(() => screen.getByTestId("series-settings-save"));
    await user.click(saveBtn);

    // useUpdateSeries(seriesId) captures the id internally, so mutate() is
    // called with just the changed payload (+ an onSuccess options object).
    expect(mock.update).toHaveBeenCalled();
    const expected: SeriesUpdate = { title: "The Expanse Saga" };
    expect(mock.update.mock.calls[0][0]).toEqual(expected);
  });

  it("renders the disabled Voice placeholder (Spec 3)", () => {
    render(<SeriesSettings seriesId="series-1" />);
    expect(screen.getByTestId("series-settings-voice-placeholder")).toBeDefined();
    expect(screen.getByText(/series\.settings\.voice\.comingInSpec3/)).toBeDefined();
  });
});
