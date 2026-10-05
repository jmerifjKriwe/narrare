/**
 * CorpusEstimateDialog tests (F3, plan Task 4 — spec §4.3/§8).
 *
 * The dialog is the honest pre-run estimate surface: it must render the
 * estimate numbers verbatim (incl. the "(of N)" clause ONLY when capped and
 * the cap_reason-keyed explanation), degrade honestly (loading / load error /
 * 422 split-first), and start the corpus pass through
 * `bulkExtractionApi.startCorpusPass`, handing the job id to `onStart`.
 *
 * The transport boundary (`@/lib/api/bulkExtraction`) is mocked; the REAL en
 * catalog resolves the copy so the assertions prove rendered text, not keys.
 *
 * @module CorpusEstimateDialog.test
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import enStudio from "../../../../i18n/messages/en/studio.json";
import { CorpusEstimateDialog } from "./CorpusEstimateDialog";

const handle = vi.hoisted(() => ({
  corpusEstimate: vi.fn(),
  startCorpusPass: vi.fn(),
}));

vi.mock("@/lib/api/bulkExtraction", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/bulkExtraction")>();
  return {
    ...actual,
    bulkExtractionApi: {
      corpusEstimate: handle.corpusEstimate,
      startCorpusPass: handle.startCorpusPass,
    },
  };
});

import { BulkExtractionApiError } from "@/lib/api/bulkExtraction";

/** Rejections are TRUE instances of the REAL error class, so the typed
 * 422 classification (`isSplitFirstBulkError`) is exercised for real. */
const apiError = (status: number, message: string) => new BulkExtractionApiError(status, message);

// The global next-intl mock (setupTests.ts) returns raw keys — resolving
// against the REAL en catalog proves the rendered copy comes from the actual
// message tree (same technique as SidebarChapterList.test.tsx).
vi.mock("next-intl", () => ({
  useTranslations:
    (namespace: string) =>
    (key: string, params?: Record<string, unknown>): string => {
      let value: unknown = { studio: enStudio };
      for (const segment of `${namespace}.${key}`.split(".")) {
        if (value && typeof value === "object") {
          value = (value as Record<string, unknown>)[segment];
        }
      }
      let text = typeof value === "string" ? value : `${namespace}.${key}`;
      if (params) {
        for (const [name, replacement] of Object.entries(params)) {
          text = text.replace(`{${name}}`, String(replacement));
        }
      }
      return text;
    },
}));

/** RULE-17 fixture — mirrors `CorpusEstimateView` (schemas_corpus.py). */
interface CorpusEstimateFixture {
  total_chapters: number;
  total_word_count: number;
  selected_chapter_ids: string[];
  chapter_count: number;
  word_count: number;
  ai_calls: number;
  capped: boolean;
  cap_reason: "chapters" | "words" | null;
}

const CAPPED_CHAPTERS: CorpusEstimateFixture = {
  total_chapters: 150,
  total_word_count: 150_000,
  selected_chapter_ids: Array.from(
    { length: 120 },
    (_, i) => `00000000-0000-4000-8000-${String(i).padStart(12, "0")}`,
  ),
  chapter_count: 120,
  word_count: 120_000,
  ai_calls: 120,
  capped: true,
  cap_reason: "chapters",
};

const UNCAPPED: CorpusEstimateFixture = {
  total_chapters: 3,
  total_word_count: 9_000,
  selected_chapter_ids: [
    "00000000-0000-4000-8000-000000000001",
    "00000000-0000-4000-8000-000000000002",
    "00000000-0000-4000-8000-000000000003",
  ],
  chapter_count: 3,
  word_count: 9_000,
  ai_calls: 3,
  capped: false,
  cap_reason: null,
};

const CAPPED_WORDS: CorpusEstimateFixture = {
  ...CAPPED_CHAPTERS,
  chapter_count: 83,
  ai_calls: 83,
  cap_reason: "words",
};

function renderDialog(overrides: { onStart?: (jobId: string) => void; open?: boolean } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onStart = overrides.onStart ?? vi.fn();
  const renderResult = render(
    <QueryClientProvider client={client}>
      <CorpusEstimateDialog
        novelId="novel-1"
        open={overrides.open ?? true}
        onOpenChange={vi.fn()}
        onStart={onStart}
      />
    </QueryClientProvider>,
  );
  return { onStart, ...renderResult };
}

beforeEach(() => {
  vi.clearAllMocks();
  handle.corpusEstimate.mockResolvedValue(UNCAPPED);
});

describe("CorpusEstimateDialog — estimate states", () => {
  it("does not fetch while closed and fetches the estimate when opened", async () => {
    const { rerender } = renderDialog({ open: false });
    expect(handle.corpusEstimate).not.toHaveBeenCalled();

    rerender(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <CorpusEstimateDialog novelId="novel-1" open onOpenChange={vi.fn()} onStart={vi.fn()} />
      </QueryClientProvider>,
    );
    await screen.findByTestId("corpus-estimate-line");
    expect(handle.corpusEstimate).toHaveBeenCalledWith("novel-1", expect.anything());
  });

  it("renders a loading state while the estimate is in flight", async () => {
    handle.corpusEstimate.mockReturnValue(new Promise(() => undefined));
    renderDialog();
    expect(screen.getByTestId("corpus-estimate-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("corpus-estimate-start-btn")).not.toBeInTheDocument();
  });

  it("renders the honest line WITHOUT an of-clause and NO cap note when uncapped", async () => {
    renderDialog();
    const line = await screen.findByTestId("corpus-estimate-line");
    expect(line.textContent).toContain("3 chapters · 9000 words · 3 AI calls");
    expect(line.textContent).not.toContain("(of");
    expect(screen.queryByTestId("corpus-cap-note")).not.toBeInTheDocument();
    expect(screen.getByTestId("corpus-pacing-note")).toBeInTheDocument();
  });

  it("renders the capped 150/120 fixture with the (of 150) clause and chapters-cap copy", async () => {
    handle.corpusEstimate.mockResolvedValue(CAPPED_CHAPTERS);
    renderDialog();

    const line = await screen.findByTestId("corpus-estimate-line");
    expect(line.textContent).toContain("120 chapters (of 150) · 120000 words · 120 AI calls");

    const capNote = screen.getByTestId("corpus-cap-note");
    // cap_reason: "chapters" keyed copy, honest about what remains (150−120).
    expect(capNote.textContent).toContain("at most 120 chapters");
    expect(capNote.textContent).toContain("remaining 30 chapters");
    expect(screen.getByTestId("corpus-pacing-note")).toBeInTheDocument();
  });

  it("renders the words-cap copy for cap_reason 'words'", async () => {
    handle.corpusEstimate.mockResolvedValue(CAPPED_WORDS);
    renderDialog();

    const capNote = await screen.findByTestId("corpus-cap-note");
    expect(capNote.textContent).toContain("200000 words");
    expect(capNote.textContent).toContain("remaining 67 chapters");
    // NOT the chapters-cap copy.
    expect(capNote.textContent).not.toContain("at most 120 chapters");
  });

  it("renders loadFailed + retry on a load error; retry refetches", async () => {
    handle.corpusEstimate.mockRejectedValueOnce(new Error("boom"));
    renderDialog();
    expect(await screen.findByTestId("corpus-estimate-error")).toBeInTheDocument();

    handle.corpusEstimate.mockResolvedValueOnce(UNCAPPED);
    fireEvent.click(screen.getByTestId("corpus-estimate-retry"));
    expect(await screen.findByTestId("corpus-estimate-line")).toBeInTheDocument();
  });

  it("renders the split-first message when the estimate 422s (oversized first chapter)", async () => {
    handle.corpusEstimate.mockRejectedValue(apiError(422, "split first"));
    renderDialog();
    expect(await screen.findByTestId("corpus-split-first-error")).toBeInTheDocument();
    expect(screen.getByText(/split the largest chapter/i)).toBeInTheDocument();
    expect(screen.queryByTestId("corpus-estimate-start-btn")).not.toBeInTheDocument();
  });
});

describe("CorpusEstimateDialog — start action", () => {
  it("Start calls startCorpusPass and hands the job id to onStart", async () => {
    const { onStart } = renderDialog();
    handle.startCorpusPass.mockResolvedValue({ job_id: "job-corpus-9" });

    fireEvent.click(await screen.findByTestId("corpus-estimate-start-btn"));

    await waitFor(() => expect(onStart).toHaveBeenCalledWith("job-corpus-9"));
    expect(handle.startCorpusPass).toHaveBeenCalledWith("novel-1");
  });

  it("disables Start while the start request is in flight", async () => {
    renderDialog();
    handle.startCorpusPass.mockReturnValue(new Promise(() => undefined));

    const start = await screen.findByTestId("corpus-estimate-start-btn");
    fireEvent.click(start);
    await waitFor(() => expect(start).toBeDisabled());
    expect(handle.startCorpusPass).toHaveBeenCalledTimes(1);
  });

  it("renders the split-first message on a 422 start and does NOT call onStart", async () => {
    const { onStart } = renderDialog();
    handle.startCorpusPass.mockRejectedValue(
      apiError(422, "Corpus pass cannot start: the novel has 0 chapters"),
    );

    fireEvent.click(await screen.findByTestId("corpus-estimate-start-btn"));

    expect(await screen.findByTestId("corpus-split-first-error")).toBeInTheDocument();
    expect(onStart).not.toHaveBeenCalled();
  });

  it("renders the catalog start-failed message on 409 (no raw server text) and does NOT call onStart", async () => {
    const { onStart } = renderDialog();
    handle.startCorpusPass.mockRejectedValue(
      apiError(409, "A bulk extraction job is already active for this novel"),
    );

    fireEvent.click(await screen.findByTestId("corpus-estimate-start-btn"));

    const err = await screen.findByTestId("corpus-start-error");
    // ADR-043 §16.5: catalog copy, never the raw server detail.
    expect(err.textContent).toContain("could not be started");
    expect(err.textContent).not.toContain("already active");
    expect(onStart).not.toHaveBeenCalled();
  });

  it("Cancel closes the dialog", async () => {
    const onOpenChange = vi.fn();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <CorpusEstimateDialog
          novelId="novel-1"
          open
          onOpenChange={onOpenChange}
          onStart={vi.fn()}
        />
      </QueryClientProvider>,
    );
    fireEvent.click(await screen.findByTestId("corpus-estimate-cancel-btn"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
