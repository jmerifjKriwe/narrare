// @vitest-environment jsdom
/**
 * The sources archive (W5 Task 6) — the harmonized `sources-archive-2` draft
 * on the shell's tokens, driven through the real API seam (the client mocked
 * at its module boundary, the house pattern). The library's real DocumentRead
 * rows: upload through the real multipart endpoint (the `file` field asserted
 * on the FormData), delete through the destructive confirm family, and the
 * semantic search round-tripping the real query into SearchHit cards (rank,
 * document title, excerpt — never an invented score or chunk/page meta). The
 * footnote/fact-check areas stand as honest disabled gaps; the empty and
 * no-hit faces answer honestly; the subbar doors connect the three sibling
 * surfaces. The face speaks du-tone in all three catalogs.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, configure, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@shell/lib/api/client")>();
  return {
    ...actual,
    client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
  };
});

import { client, type Hit, type KnowledgeDocument } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { applyLocale } from "@shell/lib/locale";
import { queryClient } from "@shell/lib/query";

import { SourcesPage } from "./SourcesPage";

const de = catalogs.de;
const api = client as unknown as Record<"GET" | "POST" | "DELETE", ReturnType<typeof vi.fn>>;

configure({ asyncUtilTimeout: 5000 });

const NOVEL_ID = "11111111-1111-1111-1111-111111111111";
const SOURCES_PATH = "/novels/$novelId/knowledge/sources";
const GRAPH_PATH = "/novels/$novelId/knowledge/graph";
const DOSSIERS_PATH = "/novels/$novelId/knowledge/dossiers";

function ok(status = 200): Response {
  return new Response(null, { status });
}

function docRow(overrides: Partial<KnowledgeDocument> & { id: string; title: string }): KnowledgeDocument {
  return {
    created_at: "2026-10-14T10:00:00Z",
    byte_size: 4_200_000,
    chunk_count: 142,
    ...overrides,
  };
}

const SURVEY = docRow({ id: "d1", title: "Groom Lake Deep Core Survey (USGS-1983-B).pdf" });
const NOTES = docRow({
  id: "d2",
  title: "Notizen zu Station 7 & Permafrost.txt",
  byte_size: 38_000,
  chunk_count: 8,
  created_at: "2026-10-18T10:00:00Z",
});
const LOGS = docRow({
  id: "d3",
  title: "Funkprotokolle 2094.md",
  byte_size: 124_000,
  chunk_count: 26,
  created_at: "2026-10-21T10:00:00Z",
});

function hitRow(overrides: Partial<Hit> & { chunk_id: string }): Hit {
  return {
    document_id: "d1",
    document_title: "Groom Lake Deep Core Survey (USGS-1983-B).pdf",
    text: "seismische Echos in einer Tiefe von 380 Metern",
    score: 0.82,
    ...overrides,
  };
}

const H1 = hitRow({ chunk_id: "c1" });
const H2 = hitRow({
  chunk_id: "c2",
  document_id: "d3",
  document_title: "Funkprotokolle 2094.md",
  text: "Signal-Laufzeit Mars-Relais zu Station 7 zeigt Schwingung bei 14.20 Hz.",
  score: 0.71,
});

let documents: KnowledgeDocument[];
let hits: Hit[];
let searchStatus: number;
let searchDetail: unknown;

function baseGet(path: string): Promise<{ data: unknown; response: Response }> {
  if (path === "/api/knowledge/documents") {
    return Promise.resolve({ data: documents, response: ok() });
  }
  if (path === "/api/writing/novels/{novel_id}") {
    return Promise.resolve({
      data: { id: NOVEL_ID, title: "Dead Signal", genre: "Mystery", blurb: null, author: null, language: "de", archived_at: null, created_at: "2026-10-01T10:00:00Z", updated_at: "2026-10-21T10:00:00Z", word_count: 1200, target_words: null, status: null, chapter_count: 3, last_exported_at: null },
      response: ok(),
    });
  }
  throw new Error(`unexpected GET: ${path}`);
}

function basePost(path: string, init?: { body?: unknown }): Promise<{ data: unknown; response: Response }> {
  if (path === "/api/knowledge/search") {
    if (searchStatus !== 200) {
      return Promise.resolve({
        data: undefined,
        error: { detail: searchDetail },
        response: ok(searchStatus),
      });
    }
    return Promise.resolve({ data: hits, response: ok() });
  }
  if (path === "/api/knowledge/documents") {
    const born = docRow({ id: "d4", title: "Neue Quelle.txt", byte_size: 1200, chunk_count: 2 });
    documents = [...documents, born];
    return Promise.resolve({ data: born, response: ok(201) });
  }
  throw new Error(`unexpected POST: ${path} ${JSON.stringify(init?.body ?? null)}`);
}

/** The page on a harness route whose id is the real sources path, beside
 *  graph and dossiers stubs the sibling doors navigate to (those pages are
 *  pinned in their own files). */
const harnessRoot = createRootRoute({ component: () => <Outlet /> });

async function renderSources(entry = `/novels/${NOVEL_ID}/knowledge/sources`) {
  const sources = createRoute({
    getParentRoute: () => harnessRoot,
    path: SOURCES_PATH,
    component: SourcesPage,
  });
  const graph = createRoute({
    getParentRoute: () => harnessRoot,
    path: GRAPH_PATH,
    component: () => <p>graph face</p>,
  });
  const dossiers = createRoute({
    getParentRoute: () => harnessRoot,
    path: DOSSIERS_PATH,
    component: () => <p>dossiers face</p>,
  });
  const router = createRouter({
    routeTree: harnessRoot.addChildren([sources, graph, dossiers]),
    history: createMemoryHistory({ initialEntries: [entry] }),
  });
  await router.load();
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

/** A text file as the picker hands it over. */
function textFile(name = "Neue Quelle.txt", size = 1200): File {
  return new File(["x".repeat(Math.min(size, 4096))], name, { type: "text/plain" });
}

function pickFile(file: File) {
  fireEvent.change(screen.getByTestId("sources-file-input"), { target: { files: [file] } });
}

beforeEach(() => {
  applyLocale("de");
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  documents = [SURVEY, NOTES, LOGS];
  hits = [H1, H2];
  searchStatus = 200;
  searchDetail = undefined;
  api.GET.mockImplementation(baseGet);
  api.POST.mockImplementation(basePost);
  api.DELETE.mockImplementation(() => Promise.resolve({ response: ok(204) }));
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("the archive lists the library's real documents", () => {
  it("renders a row per DocumentRead with the real fields only", async () => {
    await renderSources();
    const rows = await screen.findAllByTestId("sources-document");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByText(SURVEY.title)).toBeTruthy();
    // The reader's regional number format — de-DE speaks the comma.
    expect(within(rows[0]).getByText("4,2 MB")).toBeTruthy();
    expect(within(rows[0]).getByText(/Hochgeladen:/)).toBeTruthy();
    expect(within(rows[0]).getByText("142 Chunks")).toBeTruthy();
    expect(within(rows[1]).getByText("38 KB")).toBeTruthy();
    expect(within(rows[1]).getByText("8 Chunks")).toBeTruthy();
    // The read is the real list endpoint.
    expect(api.GET.mock.calls.some(([p]) => p === "/api/knowledge/documents")).toBe(true);
  });

  it("a null byte_size shows no size — the column is nullable, nothing is invented", async () => {
    documents = [docRow({ id: "d9", title: "Altlast.txt", byte_size: null, chunk_count: 3 })];
    await renderSources();
    const row = await screen.findByTestId("sources-document");
    expect(within(row).getByText("Altlast.txt")).toBeTruthy();
    expect(within(row).getByText("3 Chunks")).toBeTruthy();
    expect(within(row).queryByText(/B\b|KB|MB/)).toBeNull();
  });

  it("the meta line counts the real files and derives the extensions from the real titles", async () => {
    await renderSources();
    const meta = await screen.findByTestId("sources-file-meta");
    expect(meta.textContent).toContain("3 Dateien");
    expect(meta.textContent).toContain(".md, .pdf, .txt");
  });

  it("the header names the apparatus and the real project", async () => {
    await renderSources();
    // The title stands twice — the subbar's view label and the page h1.
    expect((await screen.findAllByText(de["knowledge.sources.title"])).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(de["knowledge.sources.eyebrow"])).toBeTruthy();
    expect(await screen.findByText("Romanprojekt Dead Signal")).toBeTruthy();
  });
});

describe("the upload fires the real multipart", () => {
  it("a text file POSTs the FormData with the API's own `file` field, then the list refetches", async () => {
    await renderSources();
    await screen.findAllByTestId("sources-document");
    const file = textFile();
    pickFile(file);
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    const [path, init] = api.POST.mock.calls.find(([p]) => p === "/api/knowledge/documents") ?? [];
    expect(path).toBe("/api/knowledge/documents");
    const body = (init as { body: FormData }).body;
    expect(body).toBeInstanceOf(FormData);
    const sent = body.get("file");
    expect(sent).toBeInstanceOf(File);
    expect((sent as File).name).toBe("Neue Quelle.txt");
    // The settled upload refetches the list — the born row stands in it.
    expect(await screen.findByText("Neue Quelle.txt")).toBeTruthy();
    expect(screen.getAllByTestId("sources-document")).toHaveLength(4);
  });

  it("the busy face holds the door while the ask is in flight", async () => {
    let resolveUpload: (value: { data: unknown; response: Response }) => void = () => {};
    api.POST.mockImplementation((path: string) => {
      if (path === "/api/knowledge/documents") {
        return new Promise((resolve) => {
          resolveUpload = resolve;
        });
      }
      return basePost(path);
    });
    await renderSources();
    await screen.findAllByTestId("sources-document");
    pickFile(textFile());
    const door = await screen.findByTestId("sources-upload");
    await waitFor(() => expect(door.getAttribute("aria-busy")).toBe("true"));
    expect((door as HTMLButtonElement).disabled).toBe(true);
    expect(door.textContent).toContain(de["knowledge.sources.uploadBusy"]);
    resolveUpload({ data: docRow({ id: "d4", title: "Neue Quelle.txt" }), response: ok(201) });
    await waitFor(() => expect((screen.getByTestId("sources-upload") as HTMLButtonElement).disabled).toBe(false));
  });

  it("an oversized file is refused before the wire — no POST, the limit named", async () => {
    await renderSources();
    await screen.findAllByTestId("sources-document");
    const big = new File(["x"], "Riesig.txt", { type: "text/plain" });
    Object.defineProperty(big, "size", { value: 1_000_001 });
    pickFile(big);
    const alert = await screen.findByTestId("sources-upload-error");
    expect(within(alert).getByText(de["knowledge.sources.uploadTooLarge"])).toBeTruthy();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("a binary file is refused before the wire — plain text only, honestly named", async () => {
    await renderSources();
    await screen.findAllByTestId("sources-document");
    pickFile(new File(["%PDF-1.4"], "Survey.pdf", { type: "application/pdf" }));
    const alert = await screen.findByTestId("sources-upload-error");
    expect(within(alert).getByText(de["knowledge.sources.uploadWrongType"])).toBeTruthy();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("the server's 413 names the size refusal", async () => {
    api.POST.mockImplementation((path: string) => {
      if (path === "/api/knowledge/documents") {
        return Promise.resolve({ data: undefined, error: { detail: "document too large" }, response: ok(413) });
      }
      return basePost(path);
    });
    await renderSources();
    await screen.findAllByTestId("sources-document");
    pickFile(textFile());
    const alert = await screen.findByTestId("sources-upload-error");
    expect(within(alert).getByText(de["knowledge.sources.uploadTooLarge"])).toBeTruthy();
  });

  it("the server's empty-document 422 names the empty refusal", async () => {
    api.POST.mockImplementation((path: string) => {
      if (path === "/api/knowledge/documents") {
        return Promise.resolve({ data: undefined, error: { detail: "document is empty" }, response: ok(422) });
      }
      return basePost(path);
    });
    await renderSources();
    await screen.findAllByTestId("sources-document");
    pickFile(textFile());
    const alert = await screen.findByTestId("sources-upload-error");
    expect(within(alert).getByText(de["knowledge.sources.uploadEmpty"])).toBeTruthy();
  });

  it("the embedding-mismatch 409 names the model change, not an outage", async () => {
    api.POST.mockImplementation((path: string) => {
      if (path === "/api/knowledge/documents") {
        return Promise.resolve({
          data: undefined,
          error: { detail: { code: "embedding-mismatch", stored: "a", found: "b" } },
          response: ok(409),
        });
      }
      return basePost(path);
    });
    await renderSources();
    await screen.findAllByTestId("sources-document");
    pickFile(textFile());
    const alert = await screen.findByTestId("sources-upload-error");
    expect(within(alert).getByText(de["knowledge.sources.mismatch"])).toBeTruthy();
  });

  it("a failed upload names itself and the retry re-fires the same file", async () => {
    let uploads = 0;
    api.POST.mockImplementation((path: string) => {
      if (path === "/api/knowledge/documents") {
        uploads += 1;
        if (uploads === 1) {
          return Promise.resolve({ data: undefined, error: { detail: "boom" }, response: ok(500) });
        }
        return basePost(path);
      }
      return basePost(path);
    });
    await renderSources();
    await screen.findAllByTestId("sources-document");
    pickFile(textFile());
    const alert = await screen.findByTestId("sources-upload-error");
    expect(within(alert).getByText(de["knowledge.sources.uploadFailed"])).toBeTruthy();
    fireEvent.click(within(alert).getByRole("button", { name: de["knowledge.graph.retry"] }));
    expect(await screen.findByText("Neue Quelle.txt")).toBeTruthy();
    expect(uploads).toBe(2);
  });
});

describe("the delete confirms in the destructive family and refetches", () => {
  it("Löschen opens the alertdialog naming the document and its chunk consequence", async () => {
    await renderSources();
    const rows = await screen.findAllByTestId("sources-document");
    fireEvent.click(within(rows[1]).getByTestId("sources-delete"));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(de["knowledge.sources.deleteTitle"])).toBeTruthy();
    expect(dialog.textContent).toContain(NOTES.title);
    expect(dialog.textContent).toContain("8 Chunks");
    // The safe answer holds the focus (the family's discipline).
    await waitFor(() =>
      expect(document.activeElement).toBe(within(dialog).getByRole("button", { name: de["knowledge.crud.cancel"] })),
    );
  });

  it("the confirm DELETEs the real id and the list refetches without the row", async () => {
    await renderSources();
    const rows = await screen.findAllByTestId("sources-document");
    fireEvent.click(within(rows[1]).getByTestId("sources-delete"));
    const dialog = await screen.findByRole("alertdialog");
    documents = documents.filter((row) => row.id !== NOTES.id);
    fireEvent.click(within(dialog).getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    await waitFor(() => expect(api.DELETE).toHaveBeenCalled());
    const [path, init] = api.DELETE.mock.calls[0];
    expect(path).toBe("/api/knowledge/documents/{document_id}");
    expect((init as { params: { path: { document_id: string } } }).params.path.document_id).toBe(NOTES.id);
    await waitFor(() => expect(screen.queryByText(NOTES.title)).toBeNull());
    expect(screen.getAllByTestId("sources-document")).toHaveLength(2);
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("cancel and Escape close without a DELETE", async () => {
    await renderSources();
    const rows = await screen.findAllByTestId("sources-document");
    fireEvent.click(within(rows[0]).getByTestId("sources-delete"));
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: de["knowledge.crud.cancel"] }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(api.DELETE).not.toHaveBeenCalled();

    fireEvent.click(within(rows[0]).getByTestId("sources-delete"));
    await screen.findByRole("alertdialog");
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(api.DELETE).not.toHaveBeenCalled();
  });

  it("a refused delete names the error inside the dialog and keeps it open", async () => {
    api.DELETE.mockImplementation(() => Promise.resolve({ response: ok(500) }));
    await renderSources();
    const rows = await screen.findAllByTestId("sources-document");
    fireEvent.click(within(rows[0]).getByTestId("sources-delete"));
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: de["knowledge.crud.deleteConfirm"] }));
    const alert = await within(dialog).findByRole("alert");
    expect(within(alert).getByText(de["knowledge.crud.deleteError"])).toBeTruthy();
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    expect(screen.getAllByTestId("sources-document")).toHaveLength(3);
  });
});

describe("the semantic search round-trips the real query", () => {
  it("the submit POSTs the real query and renders the hits' rank, title and excerpt", async () => {
    await renderSources();
    await screen.findAllByTestId("sources-document");
    fireEvent.change(screen.getByTestId("sources-search"), { target: { value: "seismische Echos" } });
    fireEvent.click(screen.getByTestId("sources-search-button"));
    await waitFor(() => expect(api.POST).toHaveBeenCalled());
    const [path, init] = api.POST.mock.calls.find(([p]) => p === "/api/knowledge/search") ?? [];
    expect(path).toBe("/api/knowledge/search");
    expect((init as { body: { query: string; limit: number } }).body).toEqual({ query: "seismische Echos", limit: 5 });
    const cards = await screen.findAllByTestId("sources-hit");
    expect(cards).toHaveLength(2);
    expect(within(cards[0]).getByText("Rang 1")).toBeTruthy();
    expect(within(cards[0]).getByText(H1.document_title)).toBeTruthy();
    expect(within(cards[0]).getByText(new RegExp(H1.text))).toBeTruthy();
    expect(within(cards[1]).getByText("Rang 2")).toBeTruthy();
    expect(within(cards[1]).getByText(H2.document_title)).toBeTruthy();
    // The count is the real number, in the locale's own plural.
    expect(screen.getByTestId("sources-hit-count").textContent).toContain("2 Treffer gefunden");
  });

  it("the hits carry no invented score, percentage or chunk/page meta", async () => {
    await renderSources();
    await screen.findAllByTestId("sources-document");
    fireEvent.change(screen.getByTestId("sources-search"), { target: { value: "Echo" } });
    fireEvent.click(screen.getByTestId("sources-search-button"));
    const cards = await screen.findAllByTestId("sources-hit");
    for (const card of cards) {
      expect(card.textContent).not.toMatch(/%|Score|Relevanz.*\d|Chunk \d|Seite \d/);
      expect(card.textContent).not.toContain("0.82");
      expect(card.textContent).not.toContain("0.71");
    }
  });

  it("an empty query asks nothing — the button waits disabled", async () => {
    await renderSources();
    await screen.findAllByTestId("sources-document");
    const button = screen.getByTestId("sources-search-button");
    expect((button as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByTestId("sources-search"), { target: { value: "   " } });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    fireEvent.submit(screen.getByTestId("sources-search-form"));
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("no hits answer the no-results face naming the query", async () => {
    hits = [];
    await renderSources();
    await screen.findAllByTestId("sources-document");
    fireEvent.change(screen.getByTestId("sources-search"), { target: { value: "Quantenresonanz" } });
    fireEvent.click(screen.getByTestId("sources-search-button"));
    const face = await screen.findByTestId("sources-no-hits");
    expect(face.textContent).toContain("Quantenresonanz");
    expect(within(face).getByText(de["knowledge.sources.noHitsNote"])).toBeTruthy();
    expect(screen.queryByTestId("sources-hit")).toBeNull();
  });

  it("a search outage names itself and the retry asks again", async () => {
    searchStatus = 500;
    await renderSources();
    await screen.findAllByTestId("sources-document");
    fireEvent.change(screen.getByTestId("sources-search"), { target: { value: "Echo" } });
    fireEvent.click(screen.getByTestId("sources-search-button"));
    const alert = await screen.findByTestId("sources-search-error");
    expect(within(alert).getByText(de["knowledge.sources.searchFailed"])).toBeTruthy();
    searchStatus = 200;
    fireEvent.click(within(alert).getByRole("button", { name: de["knowledge.graph.retry"] }));
    expect(await screen.findAllByTestId("sources-hit")).toHaveLength(2);
  });

  it("the search's embedding-mismatch 409 names the model change", async () => {
    searchStatus = 409;
    searchDetail = { code: "embedding-mismatch", stored: "a", found: "b" };
    await renderSources();
    await screen.findAllByTestId("sources-document");
    fireEvent.change(screen.getByTestId("sources-search"), { target: { value: "Echo" } });
    fireEvent.click(screen.getByTestId("sources-search-button"));
    const alert = await screen.findByTestId("sources-search-error");
    expect(within(alert).getByText(de["knowledge.sources.mismatch"])).toBeTruthy();
  });

  it("the busy face stands while the ask is in flight", async () => {
    let resolveSearch: (value: { data: unknown; response: Response }) => void = () => {};
    api.POST.mockImplementation((path: string) => {
      if (path === "/api/knowledge/search") {
        return new Promise((resolve) => {
          resolveSearch = resolve;
        });
      }
      return basePost(path);
    });
    await renderSources();
    await screen.findAllByTestId("sources-document");
    fireEvent.change(screen.getByTestId("sources-search"), { target: { value: "Echo" } });
    fireEvent.click(screen.getByTestId("sources-search-button"));
    expect(await screen.findByTestId("sources-search-busy")).toBeTruthy();
    resolveSearch({ data: hits, response: ok() });
    expect(await screen.findAllByTestId("sources-hit")).toHaveLength(2);
  });
});

describe("the honest disabled areas carry no fake content", () => {
  it("the footnote and fact-check areas stand disabled with the gap note", async () => {
    await renderSources();
    await screen.findAllByTestId("sources-document");
    const footnote = screen.getByTestId("sources-footnote-gap");
    const factCheck = screen.getByTestId("sources-factcheck-gap");
    for (const area of [footnote, factCheck]) {
      expect(area.getAttribute("aria-disabled")).toBe("true");
      expect(area.textContent).toContain(de["knowledge.sources.laterNote"]);
      expect(area.querySelectorAll("button, a, input")).toHaveLength(0);
    }
    expect(footnote.textContent).toContain(de["knowledge.sources.footnote"]);
    expect(factCheck.textContent).toContain(de["knowledge.sources.factCheck"]);
  });

  it("the view doors are disabled with the gap note — no endpoint serves the original", async () => {
    await renderSources();
    const rows = await screen.findAllByTestId("sources-document");
    const view = within(rows[0]).getByTestId("sources-view") as HTMLButtonElement;
    expect(view.disabled).toBe(true);
    expect(view.getAttribute("title")).toContain(de["knowledge.sources.viewNote"]);
    // The search result's open-original door shares the honesty.
    fireEvent.change(screen.getByTestId("sources-search"), { target: { value: "Echo" } });
    fireEvent.click(screen.getByTestId("sources-search-button"));
    const cards = await screen.findAllByTestId("sources-hit");
    const open = within(cards[0]).getByTestId("sources-open-original") as HTMLButtonElement;
    expect(open.disabled).toBe(true);
    expect(open.getAttribute("title")).toContain(de["knowledge.sources.viewNote"]);
  });
});

describe("the honest states", () => {
  it("no documents answer the upload invitation, not an outage", async () => {
    documents = [];
    await renderSources();
    const empty = await screen.findByTestId("sources-empty");
    expect(within(empty).getByText(de["knowledge.sources.empty"])).toBeTruthy();
    expect(within(empty).getByText(de["knowledge.sources.emptyNote"])).toBeTruthy();
    // The invitation is a live upload door.
    const door = within(empty).getByTestId("sources-empty-upload");
    expect((door as HTMLButtonElement).disabled).toBe(false);
    expect(screen.queryByTestId("sources-document")).toBeNull();
  });

  it("a pending ask shows the loading face, never an invented archive", async () => {
    let resolveDocs: (value: { data: unknown; response: Response }) => void = () => {};
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/documents") {
        return new Promise((resolve) => {
          resolveDocs = resolve;
        });
      }
      return baseGet(path);
    });
    await renderSources();
    expect(await screen.findByTestId("sources-loading")).toBeTruthy();
    expect(screen.queryByTestId("sources-document")).toBeNull();
    resolveDocs({ data: [SURVEY], response: ok() });
    expect(await screen.findByTestId("sources-document")).toBeTruthy();
  });

  it("an unavailable archive names itself and offers the retry", async () => {
    api.GET.mockImplementation((path: string) => {
      if (path === "/api/knowledge/documents") {
        return Promise.resolve({ data: undefined, response: ok(500) });
      }
      return baseGet(path);
    });
    await renderSources();
    const alert = await screen.findByTestId("sources-load-error");
    expect(within(alert).getByText(de["knowledge.sources.loadFailed"])).toBeTruthy();
    api.GET.mockImplementation(baseGet);
    fireEvent.click(within(alert).getByRole("button", { name: de["knowledge.graph.retry"] }));
    expect(await screen.findAllByTestId("sources-document")).toHaveLength(3);
  });
});

describe("the subbar's sibling doors connect the three surfaces", () => {
  it("the graph door opens the graph unscoped — sources carry no entity selection", async () => {
    const router = await renderSources();
    await screen.findAllByTestId("sources-document");
    fireEvent.click(screen.getByTestId("sources-graph-door"));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/knowledge/graph`));
    expect(router.state.location.search).toEqual({});
  });

  it("the dossiers door opens the dossiers unscoped", async () => {
    const router = await renderSources();
    await screen.findAllByTestId("sources-document");
    fireEvent.click(screen.getByTestId("sources-dossiers-door"));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL_ID}/knowledge/dossiers`));
    expect(router.state.location.search).toEqual({});
  });
});

describe("the face speaks du-tone in every catalog — no German fallback", () => {
  it("the English face speaks the English catalog's own copy", async () => {
    applyLocale("en");
    const en = catalogs.en;
    await renderSources();
    const rows = await screen.findAllByTestId("sources-document");
    expect(within(rows[0]).getByText("142 chunks")).toBeTruthy();
    expect(screen.getByTestId("sources-search").getAttribute("placeholder")).toBe(en["knowledge.sources.searchPlaceholder"]);
    expect(screen.getByTestId("sources-upload").textContent).toContain(en["knowledge.sources.upload"]);
    expect(screen.queryByText(de["knowledge.sources.upload"])).toBeNull();
  });

  it("the French face counts zero as one — the locale's own plural rule", async () => {
    applyLocale("fr");
    const fr = catalogs.fr;
    documents = [docRow({ id: "d9", title: "Altlast.txt", byte_size: null, chunk_count: 0 })];
    await renderSources();
    const row = await screen.findByTestId("sources-document");
    // CLDR fr puts 0 in the „one" category — the catalog's plural carries
    // the rule, never a hard-coded German zero.
    expect(within(row).getByText("0 chunk")).toBeTruthy();
    expect(screen.getByTestId("sources-search").getAttribute("placeholder")).toBe(fr["knowledge.sources.searchPlaceholder"]);
    expect(screen.queryByText(de["knowledge.sources.searchPlaceholder"])).toBeNull();
  });

  it("the three catalogs carry the sources' keys in parity, each translated and sorted", () => {
    const keys = Object.keys(catalogs.de).filter((key) => key.startsWith("knowledge.sources."));
    expect(keys.length).toBeGreaterThan(0);
    expect(keys).toEqual([...keys].sort());
    for (const locale of ["en", "fr"] as const) {
      const localeKeys = Object.keys(catalogs[locale]).filter((key) => key.startsWith("knowledge.sources."));
      expect(localeKeys, locale).toEqual(keys);
      expect(localeKeys, `${locale} sorted`).toEqual([...localeKeys].sort());
    }
    const translated = [
      "knowledge.sources.title",
      "knowledge.sources.description",
      "knowledge.sources.searchTitle",
      "knowledge.sources.empty",
      "knowledge.sources.footnote",
    ] as const;
    for (const key of translated) {
      expect(catalogs.en[key], key).not.toBe(catalogs.de[key]);
      expect(catalogs.fr[key], key).not.toBe(catalogs.de[key]);
    }
  });

  it("the German copy keeps the du register — no Sie form sneaks in", () => {
    for (const [key, value] of Object.entries(catalogs.de)) {
      if (!key.startsWith("knowledge.sources.")) continue;
      expect(value, key).not.toMatch(/\b(Sie|Ihnen|Ihr|Ihre)\b/);
    }
    expect(catalogs.de["knowledge.sources.description"]).toContain("deine");
    expect(catalogs.de["knowledge.sources.emptyNote"]).toContain("dein");
  });
});
