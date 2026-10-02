/**
 * Tests for the shared import preview panel (SETUP-003 v1).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ImportPreviewPanel } from "./ImportPreviewPanel";

// The centralized setupTests.ts next-intl mock returns i18n KEY STRINGS, but
// these tests assert rendered copy (e.g. /choose files/i, /bad UTF-8/), so the
// real "importing" catalog is served through real next-intl instead — the same
// createTranslator pattern used by SeriesDriftPanel.test.tsx.
vi.mock("next-intl", async () => {
  const actual = await vi.importActual<typeof import("next-intl")>("next-intl");
  const importing = (await import("../../../../i18n/messages/en/importing.json")).default;
  return {
    ...actual,
    useTranslations: () =>
      actual.createTranslator({ locale: "en", messages: { importing }, namespace: "importing" }),
  };
});

vi.mock("@/lib/api/client", () => ({
  importApi: {
    preview: vi.fn(),
    commit: vi.fn(),
  },
}));

import { importApi } from "@/lib/api/client";

function renderPanel(onSelectionChange: (s: unknown) => void = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ImportPreviewPanel onSelectionChange={onSelectionChange} />
    </QueryClientProvider>,
  );
}

const PREVIEW = {
  items: [
    { index: 0, suggested_title: "One", word_count: 10, source_file: "a.md" },
    { index: 1, suggested_title: "Two", word_count: 20, source_file: "a.md" },
  ],
  file_count: 1,
  chapter_count: 2,
  total_word_count: 30,
};

describe("ImportPreviewPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("previews picked files and publishes the full selection", async () => {
    const onSelectionChange = vi.fn();
    vi.mocked(importApi.preview).mockResolvedValueOnce(PREVIEW);
    renderPanel(onSelectionChange);

    const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
    const file = new File(["# One\nbody"], "a.md", { type: "text/markdown" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(screen.getByText("a.md")).toBeInTheDocument());
    // Word counts render as an explicit number (the catalog "column.words"
    // key intentionally has no {count} placeholder).
    expect(screen.getByText("Words: 10")).toBeInTheDocument();
    expect(onSelectionChange).toHaveBeenLastCalledWith({
      files: [file],
      excludedIndices: [],
      titleOverrides: {},
      includedCount: 2,
    });
  });

  it("excluding a chapter updates the published selection", async () => {
    const onSelectionChange = vi.fn();
    vi.mocked(importApi.preview).mockResolvedValueOnce(PREVIEW);
    renderPanel(onSelectionChange);

    const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], "a.md")] } });
    await waitFor(() => expect(screen.getByText("One")).toBeInTheDocument());

    fireEvent.click(screen.getAllByRole("checkbox")[1]);
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ excludedIndices: [1], includedCount: 1 }),
    );
  });

  it("renaming updates titleOverrides", async () => {
    const onSelectionChange = vi.fn();
    vi.mocked(importApi.preview).mockResolvedValueOnce(PREVIEW);
    renderPanel(onSelectionChange);

    const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], "a.md")] } });
    await waitFor(() => expect(screen.getByDisplayValue("One")).toBeInTheDocument());

    fireEvent.change(screen.getByDisplayValue("One"), { target: { value: "Renamed" } });
    expect(onSelectionChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ titleOverrides: { "0": "Renamed" } }),
    );
  });

  it("preview failure surfaces the error and publishes null", async () => {
    const onSelectionChange = vi.fn();
    vi.mocked(importApi.preview).mockRejectedValueOnce(new Error("bad UTF-8"));
    renderPanel(onSelectionChange);

    fireEvent.change(screen.getByLabelText(/choose files/i) as HTMLInputElement, {
      target: { files: [new File(["x"], "a.md")] },
    });
    await waitFor(() => expect(screen.getByText(/bad UTF-8/)).toBeInTheDocument());
    expect(onSelectionChange).toHaveBeenLastCalledWith(null);
  });
});
