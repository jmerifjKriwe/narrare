/**
 * Tests for the shared import preview panel (F1: split/merge ops).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Mock } from "vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ImportSelection } from "@/types";
import { ImportPreviewPanel } from "./ImportPreviewPanel";

// The centralized setupTests.ts next-intl mock returns i18n KEY STRINGS, but
// these tests assert rendered copy (e.g. /choose files/i, /merged 2 chapters/),
// so the real "importing" catalog is served through real next-intl instead —
// the createTranslator pattern used by ImportModal.test.tsx. Unlike that file,
// the mock honors the requested namespace: the panel uses both "importing" and
// the nested "importing.ops".
vi.mock("next-intl", async () => {
  const actual = await vi.importActual<typeof import("next-intl")>("next-intl");
  const importing = (await import("../../../../i18n/messages/en/importing.json")).default;
  return {
    ...actual,
    useTranslations: (namespace?: string) =>
      actual.createTranslator({
        locale: "en",
        messages: { importing },
        // Cast: createTranslator's namespace type is the literal registry; the
        // runtime resolves dotted sub-namespaces ("importing.ops") natively.
        namespace: (namespace ?? "importing") as "importing",
      }),
  };
});

vi.mock("@/lib/api/client", () => ({
  importApi: { preview: vi.fn(), commit: vi.fn() },
}));

import { importApi } from "@/lib/api/client";

type SelectionSpy = Mock<(selection: ImportSelection | null) => void>;
const selectionSpy = (): SelectionSpy => vi.fn<(selection: ImportSelection | null) => void>();

function renderPanel(onSelectionChange: SelectionSpy = selectionSpy()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ImportPreviewPanel onSelectionChange={onSelectionChange} />
    </QueryClientProvider>,
  );
}

const MD_PREVIEW = {
  items: [
    {
      index: 0,
      suggested_title: "Long",
      word_count: 11,
      source_file: "long.md",
      split_candidates: [
        { ordinal: 0, heading: "Scene A", words_before: 2 },
        { ordinal: 1, heading: "Scene B", words_before: 6 },
      ],
    },
    {
      index: 1,
      suggested_title: "After",
      word_count: 2,
      source_file: "next.md",
      split_candidates: [],
    },
  ],
  file_count: 1,
  chapter_count: 2,
  total_word_count: 13,
};

const V1_PREVIEW = {
  // old-server shape: no split_candidates field anywhere
  items: [{ index: 0, suggested_title: "A", word_count: 1, source_file: "a.md" }],
  file_count: 1,
  chapter_count: 1,
  total_word_count: 1,
};

const THREE_CHAPTER_PREVIEW = {
  items: [
    { index: 0, suggested_title: "One", word_count: 5, source_file: "a.md", split_candidates: [] },
    { index: 1, suggested_title: "Two", word_count: 5, source_file: "a.md", split_candidates: [] },
    {
      index: 2,
      suggested_title: "Three",
      word_count: 5,
      source_file: "b.md",
      split_candidates: [],
    },
  ],
  file_count: 2,
  chapter_count: 3,
  total_word_count: 15,
};

async function pickFiles(preview: unknown, onSelectionChange: SelectionSpy = selectionSpy()) {
  vi.mocked(importApi.preview).mockResolvedValueOnce(preview as never);
  renderPanel(onSelectionChange);
  const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["x"], "long.md")] } });
  // Generic readiness signal: the row list renders only once a preview
  // resolved (titles differ per fixture, so no single display value works).
  await waitFor(() => expect(screen.getByRole("list")).toBeInTheDocument());
  return onSelectionChange;
}

describe("ImportPreviewPanel (F1 ops)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("publishes the v2 selection shape after preview", async () => {
    const onSelectionChange = await pickFiles(MD_PREVIEW);
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        ops: { splits: {}, merges: [] },
        excludedKeys: [],
        titleByKey: {},
        includedCount: 2,
      }),
    );
  });

  it("applies a split via the picker and re-materializes rows", async () => {
    const onSelectionChange = await pickFiles(MD_PREVIEW);
    fireEvent.click(screen.getByRole("button", { name: /split/i }));

    const picker = await screen.findByTestId("split-candidate-picker");
    expect(picker).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Scene A"));
    fireEvent.click(screen.getByTestId("apply-split-btn"));

    await waitFor(() => expect(screen.getByDisplayValue("Scene A")).toBeInTheDocument());
    expect(screen.getByDisplayValue("Long")).toBeInTheDocument(); // part 0
    expect(screen.getByText("Part 1")).toBeInTheDocument();
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ ops: { splits: { 0: [0] }, merges: [] }, includedCount: 3 }),
    );
  });

  it("merges two chapters and merges the row identity into the first", async () => {
    const onSelectionChange = await pickFiles(MD_PREVIEW);
    fireEvent.click(screen.getAllByRole("button", { name: /merge with next/i })[0]);
    await waitFor(() => expect(screen.getByText(/merged 2 chapters/i)).toBeInTheDocument());
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ ops: { splits: {}, merges: [[0, 1]] }, includedCount: 1 }),
    );
  });

  it("labels the merge affordance honestly when the click lands after a run (absorption)", async () => {
    // mergeWithNext grows the run CONTAINING the clicked chapter: on the
    // chapter directly after a run, that run absorbs the row — the honest
    // label for that direction is "Merge with previous" (T5b review rider).
    const onSelectionChange = await pickFiles(THREE_CHAPTER_PREVIEW);
    fireEvent.click(screen.getAllByRole("button", { name: /merge with next/i })[0]);
    await waitFor(() => expect(screen.getByText(/merged 2 chapters/i)).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /merge with previous/i }));
    await waitFor(() => expect(screen.getByText(/merged 3 chapters/i)).toBeInTheDocument());
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ ops: { splits: {}, merges: [[0, 1, 2]] }, includedCount: 1 }),
    );
  });

  it("renames survive a subsequent merge (stable-key edits)", async () => {
    const onSelectionChange = await pickFiles(MD_PREVIEW);
    fireEvent.change(screen.getByDisplayValue("Long"), { target: { value: "Renamed" } });
    fireEvent.click(screen.getAllByRole("button", { name: /merge with next/i })[0]);
    await waitFor(() => expect(screen.getByText(/merged 2 chapters/i)).toBeInTheDocument());
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ titleByKey: { "0#0": "Renamed" } }),
    );
  });

  it("undo merge restores two rows", async () => {
    await pickFiles(MD_PREVIEW);
    fireEvent.click(screen.getAllByRole("button", { name: /merge with next/i })[0]);
    fireEvent.click(await screen.findByRole("button", { name: /undo merge/i }));
    await waitFor(() => expect(screen.getByDisplayValue("After")).toBeInTheDocument());
  });

  it("undo split restores the unsplit chapter", async () => {
    await pickFiles(MD_PREVIEW);
    fireEvent.click(screen.getByRole("button", { name: /split/i }));
    fireEvent.click(screen.getByLabelText("Scene A"));
    fireEvent.click(screen.getByTestId("apply-split-btn"));
    await waitFor(() => expect(screen.getByDisplayValue("Scene A")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /undo split/i }));
    await waitFor(() => expect(screen.queryByDisplayValue("Scene A")).not.toBeInTheDocument());
    expect(screen.getByDisplayValue("Long")).toBeInTheDocument();
  });

  it("excluding a row updates includedCount", async () => {
    const onSelectionChange = await pickFiles(MD_PREVIEW);
    fireEvent.click(screen.getAllByRole("checkbox")[1]);
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ excludedKeys: ["1#0"], includedCount: 1 }),
    );
  });

  it("hides all op controls when the server lacks the v2 field (probe)", async () => {
    await pickFiles(V1_PREVIEW);
    expect(screen.queryByRole("button", { name: /split/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /merge with next/i })).not.toBeInTheDocument();
  });

  it("publishes the v2 shape even when the server lacks the v2 field", async () => {
    // v1-server parity AFTER T7: the publish is v2-complete in every state —
    // with the ops UI gated off, ops stay EMPTY_OPS and rows are one `#0`
    // part per chapter, so stable-key edits map to v1 semantics (final ==
    // original space) through the same buildAdjustments path.
    const onSelectionChange = await pickFiles(V1_PREVIEW);
    fireEvent.click(screen.getAllByRole("checkbox")[0]);
    fireEvent.change(screen.getByDisplayValue("A"), { target: { value: "Renamed" } });

    const last = onSelectionChange.mock.lastCall?.[0];
    expect(last).not.toBeNull();
    // Pin the exact v2 member set — no v1 transition members may resurface.
    expect(Object.keys(last as object).sort()).toEqual([
      "excludedKeys",
      "files",
      "includedCount",
      "items",
      "ops",
      "titleByKey",
    ]);
    expect(last).toEqual({
      files: expect.any(Array),
      items: V1_PREVIEW.items,
      ops: { splits: {}, merges: [] },
      excludedKeys: ["0#0"],
      titleByKey: { "0#0": "Renamed" },
      includedCount: 0,
    });
  });

  it("preview failure surfaces the error and publishes null (v1 regression)", async () => {
    vi.mocked(importApi.preview).mockRejectedValueOnce(new Error("bad UTF-8"));
    const onSelectionChange = selectionSpy();
    renderPanel(onSelectionChange);
    fireEvent.change(screen.getByLabelText(/choose files/i) as HTMLInputElement, {
      target: { files: [new File(["x"], "a.md")] },
    });
    await waitFor(() => expect(screen.getByText(/bad UTF-8/)).toBeInTheDocument());
    expect(onSelectionChange).toHaveBeenLastCalledWith(null);
  });
});
