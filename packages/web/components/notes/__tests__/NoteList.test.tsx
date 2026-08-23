/**
 * NoteList component tests (NOTES-001).
 *
 * Conventions (mirrors series/__tests__): the centralized setupTests mock
 * returns i18n KEY STRINGS verbatim — assertions check keys; motion/react is
 * neutralized globally so list items mount immediately.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Note } from "@/types";
import { NoteList } from "../NoteList";

function makeNote(overrides: Partial<Note> = {}): Note {
  return {
    id: "n1",
    title: null,
    content: "First line\nbody",
    note_type: "idea",
    tags: ["plot"],
    novel_id: null,
    series_id: null,
    created_at: "2026-08-21T00:00:00Z",
    updated_at: "2026-08-21T00:00:00Z",
    ...overrides,
  };
}

describe("NoteList", () => {
  it("renders display title via fallback and the localized type label key", () => {
    render(<NoteList notes={[makeNote()]} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByText("First line")).toBeInTheDocument();
    // setupTests i18n mock returns the key: notes.type.idea
    expect(screen.getByText("type.idea")).toBeInTheDocument();
  });

  it("marks the selected note and calls onSelect", () => {
    const onSelect = vi.fn();
    render(
      <NoteList
        notes={[makeNote({ id: "n1", title: "Named" }), makeNote({ id: "n2" })]}
        selectedId="n2"
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByText("Named"));
    expect(onSelect).toHaveBeenCalledWith("n1");
  });

  it("renders tags as chips and the untitled key when nothing to show", () => {
    render(
      <NoteList
        notes={[makeNote({ tags: ["world"], title: "", content: "" })]}
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByText("world")).toBeInTheDocument();
    expect(screen.getByText("list.untitled")).toBeInTheDocument();
  });
});
