import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { chaptersApi, importApi } from "@/lib/api/client";
import enImporting from "../../../i18n/messages/en/importing.json";
import enStudio from "../../../i18n/messages/en/studio.json";
import { SidebarChapterList } from "./SidebarChapterList";

vi.mock("@/lib/api/client", () => ({
  chaptersApi: { list: vi.fn().mockResolvedValue([]), create: vi.fn() },
  volumesApi: { list: vi.fn().mockResolvedValue([]) },
  importApi: { preview: vi.fn(), commit: vi.fn() },
}));

// The corpus dialog fetches the F3 estimate/start endpoints through this
// client — mocked here so the sidebar chain test drives it without network.
const corpusApi = vi.hoisted(() => ({
  corpusEstimate: vi.fn(),
  startCorpusPass: vi.fn(),
}));

vi.mock("@/lib/api/bulkExtraction", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/bulkExtraction")>();
  return {
    ...actual,
    bulkExtractionApi: corpusApi,
  };
});

// The bulk panel is the T7 component under its own test suite; here it is the
// mount target of the sidebar's lifted bulk state. A stub asserts the WIRING
// (seeded chapter ids + close callback) without re-running a job lifecycle —
// and without firing real bulk requests against the msw unhandled-request
// guard. F3 T4: the corpus chain mounts the same panel with `initialJobId`.
vi.mock("./extraction/BulkExtractionPanel", () => ({
  BulkExtractionPanel: ({
    chapterIds,
    initialJobId,
    onClose,
  }: {
    chapterIds: readonly string[];
    initialJobId?: string;
    onClose: () => void;
  }) => (
    <button
      type="button"
      data-testid="bulk-extraction-panel"
      data-chapter-ids={chapterIds.join(",")}
      data-initial-job-id={initialJobId ?? ""}
      onClick={onClose}
    />
  ),
}));

// The global next-intl mock (setupTests.ts) returns raw keys, which would turn
// the matchers below into tautologies on key names. Resolving against the REAL
// en catalogs instead proves the rendered copy comes from the actual message
// trees — including the single-source rule that the failure banner text lives
// ONLY in importing.failedBanner (never duplicated into studio.json).
const messages: Record<string, unknown> = {
  studio: enStudio,
  importing: enImporting,
};

vi.mock("next-intl", () => ({
  useTranslations: (namespace: string) => (key: string, params?: Record<string, unknown>) => {
    let value: unknown = messages;
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

function renderList() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SidebarChapterList novelId="novel-1" />
    </QueryClientProvider>,
  );
}

/** Typed handle on the mocked chapters list loader. */
const chaptersApiList = () => vi.mocked(chaptersApi.list);

/** Full `ChapterSummary` fixture (type-check requires every field). */
const chapterSummary = (id: string, title: string, wordCount: number) => ({
  id,
  novel_id: "novel-1",
  volume_id: null,
  title,
  position: 0,
  word_count: wordCount,
  status: "draft" as const,
  updated_at: "2026-10-03T10:00:00Z",
});

describe("SidebarChapterList import entry", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it("shows an import action that opens the ImportModal", async () => {
    renderList();
    fireEvent.click(await screen.findByRole("button", { name: /import chapters/i }));
    await waitFor(() => expect(screen.getByText(/detected from frontmatter/i)).toBeInTheDocument());
  });

  it("renders the failure banner from the sessionStorage flag", async () => {
    sessionStorage.setItem("narrare:importFailed:novel-1", "1");
    renderList();
    expect(await screen.findByText(/chapters could not be imported/i)).toBeInTheDocument();
  });

  it("retry from the failure banner reopens the ImportModal", async () => {
    sessionStorage.setItem("narrare:importFailed:novel-1", "1");
    renderList();
    fireEvent.click(await screen.findByRole("button", { name: /retry import/i }));
    await waitFor(() => expect(screen.getByText(/detected from frontmatter/i)).toBeInTheDocument());
  });

  it("re-evaluates the banner when the modal closes after a successful retry", async () => {
    sessionStorage.setItem("narrare:importFailed:novel-1", "1");
    vi.mocked(importApi.commit).mockResolvedValueOnce({
      novel_id: "novel-1",
      created_count: 2,
      first_position: 0,
      last_position: 1,
      chapters: [],
    });
    renderList();
    fireEvent.click(await screen.findByRole("button", { name: /retry import/i }));

    // Pick a file through the embedded panel — the provisional selection at
    // pick time enables the commit button before any preview resolves.
    const input = (await screen.findByLabelText(/choose files/i)) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["# A\nb"], "a.md")] } });
    fireEvent.click(screen.getByTestId("import-commit-btn"));

    // Commit succeeds → the success card shows (F2 T8); the user closes via
    // "Not now" → the modal clears the key and closes → the banner must not
    // outlive the flag it mirrors (spec §6.2).
    await screen.findByTestId("import-success-card");
    expect(sessionStorage.getItem("narrare:importFailed:novel-1")).toBeNull();
    fireEvent.click(screen.getByTestId("import-notnow-btn"));

    await waitFor(() =>
      expect(screen.queryByTestId("import-failed-banner")).not.toBeInTheDocument(),
    );
  });

  it("dismissing clears the banner and the sessionStorage flag", async () => {
    sessionStorage.setItem("narrare:importFailed:novel-1", "1");
    renderList();
    fireEvent.click(await screen.findByRole("button", { name: /dismiss/i }));
    await waitFor(() =>
      expect(screen.queryByText(/chapters could not be imported/i)).not.toBeInTheDocument(),
    );
    expect(sessionStorage.getItem("narrare:importFailed:novel-1")).toBeNull();
  });
});

describe("SidebarChapterList extraction suggestion", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  const SUGGESTION = JSON.stringify({
    chapter_ids: ["c1", "c2"],
    word_count: 34,
  });

  it("renders the suggestion banner when the flag is set", async () => {
    sessionStorage.setItem("narrare:importSuggestExtract:novel-1", SUGGESTION);
    renderList();
    expect(await screen.findByTestId("import-suggest-banner")).toBeInTheDocument();
  });

  it("renders no suggestion banner when the flag is unset", async () => {
    renderList();
    // Chapters query settles first — the banner never appears at any point.
    await screen.findByTestId("new-chapter-btn");
    expect(screen.queryByTestId("import-suggest-banner")).not.toBeInTheDocument();
  });

  it("treats a corrupt flag payload as absent", async () => {
    sessionStorage.setItem("narrare:importSuggestExtract:novel-1", "not-json");
    renderList();
    await screen.findByTestId("new-chapter-btn");
    expect(screen.queryByTestId("import-suggest-banner")).not.toBeInTheDocument();
  });

  it("start clears the flag + banner and mounts the panel seeded with the stored ids", async () => {
    sessionStorage.setItem("narrare:importSuggestExtract:novel-1", SUGGESTION);
    renderList();
    fireEvent.click(await screen.findByTestId("import-suggest-start-btn"));

    const panel = await screen.findByTestId("bulk-extraction-panel");
    expect(panel).toHaveAttribute("data-chapter-ids", "c1,c2");
    await waitFor(() =>
      expect(screen.queryByTestId("import-suggest-banner")).not.toBeInTheDocument(),
    );
    expect(sessionStorage.getItem("narrare:importSuggestExtract:novel-1")).toBeNull();
  });

  it("closing the panel unmounts it (state lifted in the sidebar)", async () => {
    sessionStorage.setItem("narrare:importSuggestExtract:novel-1", SUGGESTION);
    renderList();
    fireEvent.click(await screen.findByTestId("import-suggest-start-btn"));
    await screen.findByTestId("bulk-extraction-panel");

    fireEvent.click(screen.getByTestId("bulk-extraction-panel"));
    await waitFor(() =>
      expect(screen.queryByTestId("bulk-extraction-panel")).not.toBeInTheDocument(),
    );
  });

  it("dismissing clears the suggestion banner and the sessionStorage flag", async () => {
    sessionStorage.setItem("narrare:importSuggestExtract:novel-1", SUGGESTION);
    renderList();
    fireEvent.click(await screen.findByTestId("import-suggest-dismiss-btn"));
    await waitFor(() =>
      expect(screen.queryByTestId("import-suggest-banner")).not.toBeInTheDocument(),
    );
    expect(sessionStorage.getItem("narrare:importSuggestExtract:novel-1")).toBeNull();
    expect(screen.queryByTestId("bulk-extraction-panel")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// F3 corpus pass entry (plan Task 4, D19a): sidebar entry below the import
// button → CorpusEstimateDialog → started corpus job opens the F2 panel with
// `initialJobId`. Hidden when the novel has zero chapters.
// ---------------------------------------------------------------------------

describe("SidebarChapterList corpus pass entry", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
    // vi.clearAllMocks() wipes the mockResolvedValue set in the factory —
    // restore the silent defaults the corpus dialog needs when opened.
    corpusApi.corpusEstimate.mockResolvedValue({
      total_chapters: 3,
      total_word_count: 9000,
      selected_chapter_ids: ["c1", "c2", "c3"],
      chapter_count: 3,
      word_count: 9000,
      ai_calls: 3,
      capped: false,
      cap_reason: null,
    });
  });

  it("hides the corpus entry for a novel with zero chapters", async () => {
    renderList();
    await screen.findByTestId("new-chapter-btn");
    expect(screen.queryByTestId("corpus-pass-btn")).not.toBeInTheDocument();
  });

  it("shows the corpus entry below the import button when chapters exist", async () => {
    vi.mocked(chaptersApiList()).mockResolvedValue([
      chapterSummary("c1", "Storm", 1000),
      chapterSummary("c2", "Coda", 900),
    ]);
    renderList();
    const entry = await screen.findByTestId("corpus-pass-btn");
    expect(entry).toHaveTextContent(/analyze novel corpus/i);
    // Below the import button: later sibling within the same footer container.
    const footer = entry.closest("div.p-4");
    const importBtn = footer?.querySelector('[data-testid="import-chapters-btn"]');
    expect(importBtn).not.toBeNull();
    expect(
      importBtn!.compareDocumentPosition(entry) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("opens the estimate dialog with the honest numbers from the corpus entry", async () => {
    vi.mocked(chaptersApiList()).mockResolvedValue([chapterSummary("c1", "Storm", 1000)]);
    renderList();
    fireEvent.click(await screen.findByTestId("corpus-pass-btn"));

    const line = await screen.findByTestId("corpus-estimate-line");
    expect(line.textContent).toContain("3 chapters · 9000 words · 3 AI calls");
    expect(corpusApi.corpusEstimate).toHaveBeenCalledWith("novel-1", expect.anything());
    expect(screen.queryByTestId("bulk-extraction-panel")).not.toBeInTheDocument();
  });

  it("chains entry → dialog start → panel mounted with the started corpus job id", async () => {
    vi.mocked(chaptersApiList()).mockResolvedValue([chapterSummary("c1", "Storm", 1000)]);
    corpusApi.startCorpusPass.mockResolvedValue({ job_id: "job-corpus-77" });
    renderList();
    fireEvent.click(await screen.findByTestId("corpus-pass-btn"));

    fireEvent.click(await screen.findByTestId("corpus-estimate-start-btn"));

    const panel = await screen.findByTestId("bulk-extraction-panel");
    expect(panel).toHaveAttribute("data-initial-job-id", "job-corpus-77");
    expect(corpusApi.startCorpusPass).toHaveBeenCalledWith("novel-1");
    // The dialog closes once the job is handed over.
    await waitFor(() =>
      expect(screen.queryByTestId("corpus-estimate-line")).not.toBeInTheDocument(),
    );
  });
});
