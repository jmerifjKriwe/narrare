/**
 * AddNovelToSeries component tests (Spec 1, Slice 4, Task 4.7/4.8).
 *
 * AddNovelToSeries orchestrates the join flow for the Bände list: it fetches
 * standalone novels (novels whose `series_id` is null), lets the user pick one,
 * previews the join (useJoinPreview) and applies it (useApplyJoin) via the
 * JoinPreviewDialog. It composes the presentational JoinPreviewDialog — that
 * component is exercised by its own suite; here we mock the join hooks and the
 * novels API to isolate the orchestration.
 *
 * Conventions (mirrors VolumeManagementView.test.tsx): the centralized
 * setupTests.ts mock returns i18n KEY STRINGS verbatim, so assertions check for
 * keys. A per-file QueryClientProvider wrapper is used because this component
 * owns a useQuery (standalone novels).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AddNovelToSeries } from "@/components/series/AddNovelToSeries";
import type { JoinPreview, JoinResult, NovelSummary } from "@/types";

// --- Hoisted mutable mock state ---------------------------------------------
const mock = vi.hoisted(() => ({
  standaloneNovels: [] as NovelSummary[],
  previewData: undefined as JoinPreview | undefined,
  previewMutate: vi.fn(),
  applyMutate: vi.fn(),
  previewPending: false,
  previewError: false,
  applyPending: false,
  applyError: false,
}));

vi.mock("@/lib/api/novels", () => ({
  novelsApi: {
    list: () => Promise.resolve(mock.standaloneNovels),
  },
}));

vi.mock("@/lib/hooks/useSeriesJoin", () => ({
  useJoinPreview: () => ({
    mutateAsync: (...args: unknown[]) => {
      mock.previewMutate(...args);
      return Promise.resolve(mock.previewData);
    },
    data: mock.previewData,
    isPending: mock.previewPending,
    isError: mock.previewError,
  }),
  useApplyJoin: () => ({
    mutateAsync: (...args: unknown[]) => {
      mock.applyMutate(...args);
      return Promise.resolve<JoinResult>({
        series_id: "series-1",
        novel_id: "novel-9",
        position: 3,
        promoted_to_canon: 1,
        kept_as_overlay: 0,
      });
    },
    isPending: mock.applyPending,
    isError: mock.applyError,
  }),
}));

// --- Fixtures ----------------------------------------------------------------
const previewFixture: JoinPreview = {
  series_id: "series-1",
  novel_id: "novel-9",
  canon_empty: true,
  treatments: [],
};

const novels: NovelSummary[] = [
  {
    id: "novel-9",
    series_id: null,
    title: "Leviathan Wakes",
    author: "Corey",
    genre: "sci-fi",
    writing_language: "en",
    is_demo: false,
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "novel-10",
    series_id: null,
    title: "Caliban's War",
    author: "Corey",
    genre: "sci-fi",
    writing_language: "en",
    is_demo: false,
    updated_at: "2026-01-02T00:00:00Z",
  },
];

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("AddNovelToSeries", () => {
  beforeEach(() => {
    mock.standaloneNovels = [...novels];
    mock.previewData = previewFixture;
    mock.previewMutate = vi.fn();
    mock.applyMutate = vi.fn();
    mock.previewPending = false;
    mock.previewError = false;
    mock.applyPending = false;
    mock.applyError = false;
  });

  it("lists standalone novels as select options", async () => {
    renderWithProviders(<AddNovelToSeries seriesId="series-1" nextPosition={3} />);
    await waitFor(() => {
      expect(screen.getByText("Leviathan Wakes")).toBeDefined();
    });
    expect(screen.getByText("Caliban's War")).toBeDefined();
  });

  it("disables the Add Novel button until a novel is selected", async () => {
    renderWithProviders(<AddNovelToSeries seriesId="series-1" nextPosition={3} />);
    await waitFor(() => {
      expect(screen.getByText("Leviathan Wakes")).toBeDefined();
    });
    const addBtn = screen.getByTestId("add-novel-to-series") as HTMLButtonElement;
    expect(addBtn.disabled).toBe(true);
  });

  it("shows an empty hint and disables the button when there are no standalone novels", async () => {
    mock.standaloneNovels = [];
    renderWithProviders(<AddNovelToSeries seriesId="series-1" nextPosition={1} />);
    await waitFor(() => {
      expect(screen.getByTestId("add-novel-empty")).toBeDefined();
    });
    expect((screen.getByTestId("add-novel-to-series") as HTMLButtonElement).disabled).toBe(true);
  });

  it("previews the join and opens the dialog when Add Novel is clicked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AddNovelToSeries seriesId="series-1" nextPosition={3} />);
    await waitFor(() => {
      expect(screen.getByText("Leviathan Wakes")).toBeDefined();
    });

    await user.selectOptions(screen.getByTestId("add-novel-select"), "novel-9");
    await user.click(screen.getByTestId("add-novel-to-series"));

    expect(mock.previewMutate).toHaveBeenCalledWith("novel-9");
    await waitFor(() => {
      expect(screen.getByTestId("join-preview-dialog")).toBeDefined();
    });
  });

  it("applies the join with the chosen novel and next position, then closes", async () => {
    const onAdded = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <AddNovelToSeries seriesId="series-1" nextPosition={3} onAdded={onAdded} />,
    );
    await waitFor(() => {
      expect(screen.getByText("Leviathan Wakes")).toBeDefined();
    });

    await user.selectOptions(screen.getByTestId("add-novel-select"), "novel-9");
    await user.click(screen.getByTestId("add-novel-to-series"));
    await waitFor(() => {
      expect(screen.getByTestId("join-preview-dialog")).toBeDefined();
    });

    await user.click(screen.getByTestId("join-preview-confirm"));

    await waitFor(() => {
      expect(mock.applyMutate).toHaveBeenCalledWith({ novelId: "novel-9", position: 3 });
    });
    await waitFor(() => {
      expect(onAdded).toHaveBeenCalledOnce();
    });
    await waitFor(() => {
      expect(screen.queryByTestId("join-preview-dialog")).toBeNull();
    });
  });
});
