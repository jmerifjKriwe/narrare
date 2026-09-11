/**
 * NoteEditor component tests (NOTES-001).
 *
 * The editor is controlled: mutations run through the shared hooks and are
 * mocked via MSW; assertions cover prefill, edit + save callback, preview
 * toggle rendering markdownToHtml output, delete confirmation flow, and the
 * discuss callback.
 *
 * Binding T23→T26 review coverage lives here too: the draft lifecycle is
 * keyed by note IDENTITY (note.id), so a background refetch replacing the
 * note OBJECT must not clobber the in-progress draft; and the PATCH body
 * must encode the link-clear semantics (explicit null clears a stored link,
 * never-set links stay absent) plus the novel-XOR-series scope invariant.
 *
 * Conventions (mirrors series/__tests__ + SessionPanel):
 * - Query-hook components render inside a fresh QueryClientProvider
 *   (setupTests provides no global one).
 * - The MSW guard requires handlers for every request made: novels has a
 *   default handler, the series list does not — renderEditor installs one.
 * - The centralized next-intl mock returns KEY STRINGS verbatim.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/toaster";
import { server } from "@/mocks/server";
import type { Note } from "@/types";
import { NoteEditor } from "../NoteEditor";

const baseNote: Note = {
  id: "n1",
  title: "Twist",
  content: "The **aunt** did it",
  note_type: "idea",
  tags: ["plot"],
  novel_id: null,
  series_id: null,
  created_at: "2026-08-21T00:00:00Z",
  updated_at: "2026-08-21T00:00:00Z",
};

type EditorProps = Parameters<typeof NoteEditor>[0];

function renderEditor(overrides: Partial<EditorProps> = {}, series: unknown[] = []) {
  // GET /api/v1/series has no default handler — the unhandled-request guard
  // would fail whichever test mounted the link dropdowns. The response is a
  // parameter because the query resolves INSIDE render's act flush: a later
  // server.use override would never reach the already-finished fetch.
  server.use(http.get("*/api/v1/series", () => HttpResponse.json(series)));

  const onSaved = vi.fn();
  const onDeleted = vi.fn();
  const onDiscuss = vi.fn();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const props: EditorProps = {
    note: baseNote,
    availableTags: ["plot", "world"],
    onSaved,
    onDeleted,
    onDiscuss,
    ...overrides,
  };
  const withChrome = (next: EditorProps = props) => (
    <QueryClientProvider client={queryClient}>
      <NoteEditor {...next} />
      {/* Real Toaster so sonner error toasts are assertable in the DOM. */}
      <Toaster />
    </QueryClientProvider>
  );
  const utils = render(withChrome());
  return {
    ...utils,
    onSaved,
    onDeleted,
    onDiscuss,
    rerenderWith: (next: Partial<EditorProps>) => utils.rerender(withChrome({ ...props, ...next })),
  };
}

describe("NoteEditor", () => {
  it("renders fields prefilled from the note", () => {
    renderEditor();
    expect(screen.getByDisplayValue("Twist")).toBeInTheDocument();
    expect(screen.getByDisplayValue("The **aunt** did it")).toBeInTheDocument();
    expect(screen.getByTestId("tag-chips")).toHaveTextContent("plot");
  });

  it("saves edits through PATCH and emits onSaved", async () => {
    server.use(
      http.patch("*/api/v1/notes/:id", async () =>
        HttpResponse.json({ ...baseNote, content: "edited body" }),
      ),
    );
    const { onSaved } = renderEditor();
    const content = screen.getByTestId("note-content-input");
    fireEvent.change(content, { target: { value: "edited body" } });
    fireEvent.click(screen.getByTestId("note-save-button"));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("toggles markdown preview rendered via markdownToHtml", () => {
    renderEditor();
    fireEvent.click(screen.getByTestId("note-preview-toggle"));
    const preview = screen.getByTestId("note-preview");
    expect(preview.innerHTML).toContain("<strong>aunt</strong>");
  });

  it("requires confirmation before delete and emits onDeleted", async () => {
    server.use(http.delete("*/api/v1/notes/:id", () => new HttpResponse(null, { status: 204 })));
    const { onDeleted } = renderEditor();
    fireEvent.click(screen.getByTestId("note-delete-button"));
    expect(screen.getByText("editor.deleteTitle")).toBeInTheDocument(); // i18n key mock
    fireEvent.click(screen.getByTestId("confirm-dialog-confirm"));
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
  });

  it("emits onDiscuss with the note id", () => {
    const { onDiscuss } = renderEditor();
    fireEvent.click(screen.getByTestId("note-discuss-button"));
    expect(onDiscuss).toHaveBeenCalledWith(baseNote.id);
  });

  it("keeps the in-progress draft when a refetch replaces the note object (same id)", () => {
    const { rerenderWith } = renderEditor();
    fireEvent.change(screen.getByTestId("note-content-input"), {
      target: { value: "wip draft" },
    });
    // Background refetch: NEW object identity, SAME note id, changed content.
    rerenderWith({ note: { ...baseNote, content: "server content" } });
    expect(screen.getByTestId("note-content-input")).toHaveValue("wip draft");
  });

  it("refills the draft when the pane switches to a different note", () => {
    const { rerenderWith } = renderEditor();
    fireEvent.change(screen.getByTestId("note-content-input"), {
      target: { value: "wip draft" },
    });
    rerenderWith({
      note: { ...baseNote, id: "n2", title: null, content: "second note body" },
    });
    expect(screen.getByTestId("note-content-input")).toHaveValue("second note body");
  });

  it("PATCH body: clearing a stored link sends explicit null, never-set links stay absent", async () => {
    let captured: Record<string, unknown> | undefined;
    server.use(
      http.patch("*/api/v1/notes/:id", async ({ request }) => {
        captured = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(baseNote);
      }),
    );
    renderEditor({ note: { ...baseNote, novel_id: "novel-1" } });
    fireEvent.change(screen.getByTestId("note-novel-link"), { target: { value: "" } });
    fireEvent.click(screen.getByTestId("note-save-button"));
    await waitFor(() => expect(captured).toBeDefined());
    // Stored link cleared → explicit null (PATCH exclude_unset semantics).
    expect(captured?.novel_id).toBeNull();
    // Never-set link → field absent, not null (server keeps it untouched).
    expect(captured).not.toHaveProperty("series_id");
  });

  it("PATCH body keeps the scope invariant: linking a series nulls the stored novel link", async () => {
    let captured: Record<string, unknown> | undefined;
    server.use(
      http.patch("*/api/v1/notes/:id", async ({ request }) => {
        captured = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(baseNote);
      }),
    );
    renderEditor({ note: { ...baseNote, novel_id: "novel-1" } }, [
      { id: "sr1", title: "Northern Light", subtitle: null },
    ]);
    // The series options arrive async via MSW — wait for the option before
    // changing the controlled select, or the value cannot stick.
    await screen.findByText("Northern Light");
    fireEvent.change(screen.getByTestId("note-series-link"), { target: { value: "sr1" } });
    fireEvent.click(screen.getByTestId("note-save-button"));
    await waitFor(() => expect(captured).toBeDefined());
    expect(captured?.series_id).toBe("sr1");
    expect(captured?.novel_id).toBeNull();
  });

  it("shows an error toast and stays open when delete fails", async () => {
    server.use(http.delete("*/api/v1/notes/:id", () => new HttpResponse(null, { status: 500 })));
    const { onDeleted } = renderEditor();
    fireEvent.click(screen.getByTestId("note-delete-button"));
    fireEvent.click(screen.getByTestId("confirm-dialog-confirm"));
    expect(await screen.findByText("editor.deleteFailed")).toBeInTheDocument();
    expect(onDeleted).not.toHaveBeenCalled();
  });
});
