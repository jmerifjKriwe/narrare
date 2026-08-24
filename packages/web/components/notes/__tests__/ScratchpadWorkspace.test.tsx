/**
 * ScratchpadWorkspace tests (NOTES-001): empty state first capture, list
 * rendering + selection, semantic-mode honest badge.
 *
 * Conventions (mirrors NoteEditor.test.tsx):
 * - Query-hook components render inside a fresh QueryClientProvider
 *   (setupTests provides no global one; retry disabled for fast failures).
 * - The MSW guard requires handlers for every request made: novels has a
 *   default handler, series/notes do not — renderWorkspace tests install
 *   them.
 * - The centralized next-intl mock returns KEY STRINGS verbatim.
 *
 * Beyond the brief's three cases, this file pins the binding review
 * constraints: the T21 Enter-on-empty-search guard + tag dedupe, the T21b
 * scope-filter feed (novels/series/hasLinks + stale-scope clearing), the
 * honest "notes exist, none selected" right pane (no false "empty" copy),
 * and the T23 memoized-by-id editor stability across background refetches.
 * Final-review additions: filtered-zero must NOT show the capture card
 * (existence comes from the unfiltered probe), and a capture whose POST
 * races a filter change must still visibly select the new note.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { notesKeys } from "@/lib/hooks/notesKeys";
import { novelsKeys } from "@/lib/hooks/novelsKeys";
import { server } from "@/mocks/server";
import type { Note } from "@/types";
import { ScratchpadWorkspace } from "../ScratchpadWorkspace";

const emptyNoteList = http.get("*/api/v1/notes", () => HttpResponse.json([]));
const emptyTags = http.get("*/api/v1/notes/tags", () => HttpResponse.json({ tags: [] }));
const emptyNovels = http.get("*/api/v1/novels", () => HttpResponse.json([]));
const emptySeries = http.get("*/api/v1/series", () => HttpResponse.json([]));

const note = (id: string, overrides: Partial<Note> = {}): Note => ({
  id,
  title: null,
  content: `content ${id}`,
  note_type: "idea",
  tags: [],
  novel_id: null,
  series_id: null,
  created_at: "2026-08-21T00:00:00Z",
  updated_at: "2026-08-21T00:00:00Z",
  ...overrides,
});

function renderWorkspace() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <ScratchpadWorkspace />
    </QueryClientProvider>,
  );
  return { ...utils, queryClient };
}

describe("ScratchpadWorkspace", () => {
  it("shows the empty state when no notes exist", async () => {
    server.use(emptyNoteList, emptyTags, emptyNovels, emptySeries);
    // Brief deviation (T23 precedent): the workspace consumes query hooks,
    // so it renders inside a fresh QueryClientProvider (setupTests provides
    // no global one).
    renderWorkspace();
    expect(await screen.findByTestId("scratchpad-empty")).toBeInTheDocument();
  });

  it("creates the first note from the empty-state card", async () => {
    server.use(emptyNoteList, emptyTags, emptyNovels, emptySeries);
    server.use(
      http.post("*/api/v1/notes", async () =>
        HttpResponse.json(
          {
            id: "n1",
            title: null,
            content: "captured thought",
            note_type: "idea",
            tags: [],
            novel_id: null,
            series_id: null,
            created_at: "2026-08-21T00:00:00Z",
            updated_at: "2026-08-21T00:00:00Z",
          },
          { status: 201 },
        ),
      ),
    );
    renderWorkspace();
    const textarea = await screen.findByTestId("empty-capture-text");
    fireEvent.change(textarea, { target: { value: "captured thought" } });
    fireEvent.click(screen.getByTestId("empty-capture-save"));
    // After create the list refetches and now shows the note.
    server.use(
      http.get("*/api/v1/notes", () =>
        HttpResponse.json([
          {
            id: "n1",
            title: null,
            content: "captured thought",
            note_type: "idea",
            tags: [],
            novel_id: null,
            series_id: null,
            created_at: "2026-08-21T00:00:00Z",
            updated_at: "2026-08-21T00:00:00Z",
          },
        ]),
      ),
    );
    await waitFor(() => expect(screen.getByTestId("note-list-item-n1")).toBeInTheDocument());
  });

  it("shows the honest lexical badge on fallback search results", async () => {
    server.use(emptyNovels, emptySeries);
    server.use(
      http.get("*/api/v1/notes", () => HttpResponse.json([])),
      http.get("*/api/v1/notes/tags", () => HttpResponse.json({ tags: [] })),
      http.post("*/api/v1/notes/search", async () =>
        HttpResponse.json({
          mode: "lexical",
          query: "aunt",
          results: [
            {
              id: "n1",
              title: null,
              content: "the aunt did it",
              note_type: "idea",
              tags: [],
              novel_id: null,
              series_id: null,
              created_at: "2026-08-21T00:00:00Z",
              updated_at: "2026-08-21T00:00:00Z",
              similarity: null,
            },
          ],
        }),
      ),
    );
    renderWorkspace();
    const search = await screen.findByTestId("note-search-input");
    fireEvent.change(search, { target: { value: "aunt" } });
    fireEvent.click(screen.getByTestId("note-semantic-toggle"));
    fireEvent.keyDown(search, { key: "Enter" });
    expect(await screen.findByTestId("note-search-mode-badge")).toHaveTextContent(
      "search.lexicalBadge",
    );
  });

  it("does not fire semantic search on Enter with an empty query (T21 guard)", async () => {
    let searchCalled = false;
    server.use(emptyNovels, emptySeries);
    server.use(
      http.get("*/api/v1/notes", () => HttpResponse.json([])),
      http.get("*/api/v1/notes/tags", () => HttpResponse.json({ tags: [] })),
      http.post("*/api/v1/notes/search", () => {
        searchCalled = true;
        return HttpResponse.json({ mode: "lexical", query: "", results: [] });
      }),
    );
    renderWorkspace();
    const search = await screen.findByTestId("note-search-input");
    fireEvent.click(screen.getByTestId("note-semantic-toggle"));
    fireEvent.keyDown(search, { key: "Enter" });
    expect(searchCalled).toBe(false);
    expect(screen.queryByTestId("note-search-mode-badge")).not.toBeInTheDocument();
  });

  it("dedupes available tags before feeding the filter combobox (T21)", async () => {
    server.use(emptyNoteList, emptyNovels, emptySeries);
    server.use(
      http.get("*/api/v1/notes/tags", () => HttpResponse.json({ tags: ["plot", "plot", "poem"] })),
    );
    renderWorkspace();
    const input = await screen.findByTestId("note-filter-tag-input");
    fireEvent.change(input, { target: { value: "p" } });
    expect(await screen.findByTestId("note-filter-tag-suggestion-poem")).toBeInTheDocument();
    // "plot" arrives twice from the endpoint but may surface once.
    expect(screen.getAllByTestId("note-filter-tag-suggestion-plot")).toHaveLength(1);
  });

  it("shows a select prompt, not the capture card, when notes exist but none is selected", async () => {
    server.use(emptyTags, emptyNovels, emptySeries);
    server.use(http.get("*/api/v1/notes", () => HttpResponse.json([note("n1")])));
    renderWorkspace();
    await screen.findByTestId("note-list-item-n1");
    expect(screen.queryByTestId("scratchpad-empty")).not.toBeInTheDocument();
    expect(screen.getByText("empty.selectPrompt")).toBeInTheDocument();
  });

  it("keeps the capture card hidden when notes exist but the filter matches none (final review)", async () => {
    // The handler honors note_type so probe (unfiltered) and filtered list
    // diverge: one "concept" note exists, the "question" filter matches none.
    server.use(
      emptyTags,
      emptyNovels,
      emptySeries,
      http.get("*/api/v1/notes", ({ request }) => {
        const type = new URL(request.url).searchParams.get("note_type");
        const all = [note("n1", { note_type: "concept" })];
        return HttpResponse.json(type ? all.filter((n) => n.note_type === type) : all);
      }),
    );
    renderWorkspace();
    await screen.findByTestId("note-list-item-n1");
    fireEvent.change(screen.getByTestId("note-type-filter"), { target: { value: "question" } });
    // The rail honestly reports no match; the pane stays quiet — never the
    // "Nothing captured yet" card while notes exist.
    expect(await screen.findByTestId("note-list-empty")).toHaveTextContent("list.noResults");
    expect(screen.getByTestId("scratchpad-select-prompt")).toBeInTheDocument();
    expect(screen.queryByTestId("scratchpad-empty")).not.toBeInTheDocument();
  });

  it("still selects visibly when a filter is set while the capture POST is in flight (final review)", async () => {
    let notes: Note[] = [];
    server.use(
      emptyTags,
      emptyNovels,
      emptySeries,
      http.get("*/api/v1/notes", ({ request }) => {
        const type = new URL(request.url).searchParams.get("note_type");
        return HttpResponse.json(type ? notes.filter((n) => n.note_type === type) : notes);
      }),
      http.post("*/api/v1/notes", async () => {
        await new Promise((resolve) => setTimeout(resolve, 25));
        notes = [note("n1", { content: "captured thought", note_type: "idea" })];
        return HttpResponse.json(notes[0], { status: 201 });
      }),
    );
    renderWorkspace();
    fireEvent.change(await screen.findByTestId("empty-capture-text"), {
      target: { value: "captured thought" },
    });
    fireEvent.click(screen.getByTestId("empty-capture-save"));
    // Mid-flight the user narrows the type filter to one the new "idea"
    // note does not match — the capture must still land on a selected,
    // editable note (filters reset), not silently no-op.
    fireEvent.change(screen.getByTestId("note-type-filter"), { target: { value: "question" } });
    expect(await screen.findByTestId("note-content-input")).toHaveValue("captured thought");
    expect(screen.getByTestId("note-list-item-n1")).toBeInTheDocument();
  });

  it("feeds the scope filter from linked notes and clears it when its target vanishes (T21b)", async () => {
    const listQueries: string[] = [];
    server.use(
      http.get("*/api/v1/notes", ({ request }) => {
        listQueries.push(new URL(request.url).search);
        return HttpResponse.json([note("n1", { novel_id: "nv1" })]);
      }),
      http.get("*/api/v1/notes/tags", () => HttpResponse.json({ tags: [] })),
      http.get("*/api/v1/novels", () =>
        HttpResponse.json([{ id: "nv1", title: "The Lighthouse" }]),
      ),
      http.get("*/api/v1/series", () => HttpResponse.json([])),
    );
    const { queryClient } = renderWorkspace();
    // hasLinks: the loaded note is linked → the scope select is mounted.
    const scope = await screen.findByTestId("note-scope-filter");
    fireEvent.change(scope, { target: { value: "novel:nv1" } });
    await waitFor(() => expect(listQueries.some((q) => q.includes("novel_id=nv1"))).toBe(true));
    // The novel list refetches without the scoped novel → the workspace must
    // clear the stale scope (parent responsibility per NoteScopeSelect JSDoc).
    server.use(http.get("*/api/v1/novels", () => HttpResponse.json([])));
    await queryClient.invalidateQueries({ queryKey: novelsKeys.all });
    await waitFor(() => expect(listQueries.at(-1) ?? "").not.toContain("novel_id"));
    await waitFor(() => expect(screen.queryByTestId("note-scope-filter")).not.toBeInTheDocument());
  });

  it("clears search results when a stale scope is auto-reset (follow-up P-FE3)", async () => {
    server.use(
      http.get("*/api/v1/notes", () => HttpResponse.json([note("n1", { novel_id: "nv1" })])),
      http.get("*/api/v1/notes/tags", () => HttpResponse.json({ tags: [] })),
      http.get("*/api/v1/novels", () =>
        HttpResponse.json([{ id: "nv1", title: "The Lighthouse" }]),
      ),
      http.get("*/api/v1/series", () => HttpResponse.json([])),
      http.post("*/api/v1/notes/search", () =>
        HttpResponse.json({
          mode: "lexical",
          query: "aunt",
          results: [{ ...note("n1", { novel_id: "nv1" }), similarity: null }],
        }),
      ),
    );
    const { queryClient } = renderWorkspace();
    const scope = await screen.findByTestId("note-scope-filter");
    fireEvent.change(scope, { target: { value: "novel:nv1" } });
    // Scoped semantic search succeeds → the honest mode badge shows.
    const search = screen.getByTestId("note-search-input");
    fireEvent.change(search, { target: { value: "aunt" } });
    fireEvent.click(screen.getByTestId("note-semantic-toggle"));
    fireEvent.keyDown(search, { key: "Enter" });
    expect(await screen.findByTestId("note-search-mode-badge")).toBeInTheDocument();
    // The scoped novel vanishes → the auto-reset must ALSO invalidate the
    // search results produced under that scope (same path as user changes).
    server.use(http.get("*/api/v1/novels", () => HttpResponse.json([])));
    await queryClient.invalidateQueries({ queryKey: novelsKeys.all });
    await waitFor(() =>
      expect(screen.queryByTestId("note-search-mode-badge")).not.toBeInTheDocument(),
    );
  });

  it("keeps the editor and its draft across a background refetch of the same note (T23)", async () => {
    let listFetches = 0;
    // One counting handler whose body flips between fetches (a second
    // server.use override would silently swallow the counter).
    let listBody = [note("n1", { content: "original content" })];
    server.use(
      http.get("*/api/v1/notes", () => {
        listFetches += 1;
        return HttpResponse.json(listBody);
      }),
      emptyTags,
      emptyNovels,
      emptySeries,
    );
    const { queryClient } = renderWorkspace();
    fireEvent.click(await screen.findByTestId("note-list-item-n1"));
    const content = await screen.findByTestId("note-content-input");
    expect(content).toHaveValue("original content");
    fireEvent.change(content, { target: { value: "wip draft" } });
    // Background refetch replaces the note OBJECT (new content) — the editor
    // must not remount and must not clobber the in-progress draft.
    listBody = [note("n1", { content: "server content" })];
    await queryClient.invalidateQueries({ queryKey: notesKeys.all });
    await waitFor(() => expect(listFetches).toBeGreaterThanOrEqual(2));
    const after = screen.getByTestId("note-content-input");
    expect(after).toBe(content);
    expect(after).toHaveValue("wip draft");
  });
});
