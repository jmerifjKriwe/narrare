/**
 * NoteList component tests (NOTES-001).
 *
 * Conventions (mirrors series/__tests__): the centralized setupTests mock
 * returns i18n KEY STRINGS verbatim — assertions check keys; motion/react is
 * neutralized globally so list items mount immediately.
 *
 * Local next-intl override (sanctioned by setupTests' "individual test mocks
 * can still override"): the global mock returns keys verbatim, which DROPS
 * t() params — but the updated-date test must see the useFormatter output to
 * prove the date is locale-formatted (P-FE1). A minimal message table keeps
 * every other assertion key-verbatim.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Note } from "@/types";
import { NoteList } from "../NoteList";

vi.mock("next-intl", () => ({
  useFormatter: () => ({
    dateTime: (value: Date) => value.toISOString().slice(0, 10),
  }),
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    const messages: Record<string, string> = {
      "list.updated": "Updated {date}",
    };
    const template = messages[key] ?? key;
    if (!params) return template;
    return Object.entries(params).reduce(
      (str, [k, v]) => str.replaceAll(`{${k}}`, String(v)),
      template,
    );
  },
}));

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

  it("formats the updated date via next-intl useFormatter, not the browser locale", () => {
    // Regression (P-FE1): the list must not use toLocaleDateString() (whose
    // output varies with the browser locale); the date comes from
    // useFormatter (app locale, medium date style — SeriesDriftPanel's ICU
    // convention). The mocked formatter renders the ISO date, which no
    // toLocaleDateString() locale produces for this instant.
    render(<NoteList notes={[makeNote()]} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByText("Updated 2026-08-21")).toBeInTheDocument();
  });
});
