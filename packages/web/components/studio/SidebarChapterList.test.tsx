import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { importApi } from "@/lib/api/client";
import enImporting from "../../../i18n/messages/en/importing.json";
import enStudio from "../../../i18n/messages/en/studio.json";
import { SidebarChapterList } from "./SidebarChapterList";

vi.mock("@/lib/api/client", () => ({
  chaptersApi: { list: vi.fn().mockResolvedValue([]), create: vi.fn() },
  volumesApi: { list: vi.fn().mockResolvedValue([]) },
  importApi: { preview: vi.fn(), commit: vi.fn() },
}));

// The bulk panel is the T7 component under its own test suite; here it is the
// mount target of the sidebar's lifted bulk state. A stub asserts the WIRING
// (seeded chapter ids + close callback) without re-running a job lifecycle —
// and without firing real bulk requests against the msw unhandled-request
// guard.
vi.mock("./extraction/BulkExtractionPanel", () => ({
  BulkExtractionPanel: ({
    chapterIds,
    onClose,
  }: {
    chapterIds: readonly string[];
    onClose: () => void;
  }) => (
    <button
      type="button"
      data-testid="bulk-extraction-panel"
      data-chapter-ids={chapterIds.join(",")}
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
