/**
 * NoteEditor component tests (NOTES-001).
 *
 * The editor is controlled: mutations run through the shared hooks and are
 * mocked via MSW; assertions cover prefill, edit + save callback, preview
 * toggle rendering markdownToHtml output, delete confirmation flow, and the
 * discuss callback.
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

function renderEditor(overrides: Partial<Parameters<typeof NoteEditor>[0]> = {}) {
  // GET /api/v1/series has no default handler — the unhandled-request guard
  // would fail whichever test mounted the link dropdowns.
  server.use(http.get("*/api/v1/series", () => HttpResponse.json([])));

  const onSaved = vi.fn();
  const onDeleted = vi.fn();
  const onDiscuss = vi.fn();
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <NoteEditor
        note={baseNote}
        availableTags={["plot", "world"]}
        onSaved={onSaved}
        onDeleted={onDeleted}
        onDiscuss={onDiscuss}
        {...overrides}
      />
    </QueryClientProvider>,
  );
  return { onSaved, onDeleted, onDiscuss };
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
});
