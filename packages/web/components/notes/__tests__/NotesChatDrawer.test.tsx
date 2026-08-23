/**
 * NotesChatDrawer tests (NOTES-001 §6b/§7): renders the chat surface for a
 * (possibly global) note, with the attached-note banner and close handling.
 * ChatPanel internals are out of scope here — they are covered by the
 * existing editor chat tests; this test asserts composition + banner.
 *
 * next-intl is mocked LOCALLY (overriding the centralized setupTests mock,
 * which returns i18n keys verbatim): the banner assertions require real
 * message templates with {title} interpolation. Same pattern as
 * ChatPanel.error.test.tsx. Unknown keys (ChatPanel's "studio" namespace)
 * fall back to the key string — those internals are covered elsewhere.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Note } from "@/types";
import { NotesChatDrawer } from "../NotesChatDrawer";

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    const translations: Record<string, string> = {
      "chat.attachedNote": "Discussing note: {title}",
      "list.untitled": "Untitled",
      "editor.discuss": "Discuss in chat",
    };
    const template = translations[key] ?? key;
    if (params) {
      return Object.entries(params).reduce(
        (str, [k, v]) => str.replace(`{${k}}`, String(v)),
        template,
      );
    }
    return template;
  },
  useLocale: () => "en",
  useNow: () => new Date("2024-01-01"),
  useTimeZone: () => "UTC",
}));

const note: Note = {
  id: "n1",
  title: "Twist",
  content: "The aunt did it",
  note_type: "idea",
  tags: [],
  novel_id: null,
  series_id: null,
  created_at: "2026-08-21T00:00:00Z",
  updated_at: "2026-08-21T00:00:00Z",
};

describe("NotesChatDrawer", () => {
  it("renders nothing when closed", () => {
    const { container } = render(<NotesChatDrawer open={false} onClose={vi.fn()} note={note} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the attached-note banner with the note title", () => {
    render(<NotesChatDrawer open onClose={vi.fn()} note={note} />);
    expect(screen.getByTestId("note-chat-banner")).toHaveTextContent("Twist");
  });

  it("falls back to the derived title when the note has none", () => {
    render(<NotesChatDrawer open onClose={vi.fn()} note={{ ...note, title: null }} />);
    expect(screen.getByTestId("note-chat-banner")).toHaveTextContent("The aunt did it");
  });

  it("calls onClose from the drawer close button", () => {
    const onClose = vi.fn();
    render(<NotesChatDrawer open onClose={onClose} note={note} />);
    fireEvent.click(screen.getByTestId("note-chat-close"));
    expect(onClose).toHaveBeenCalled();
  });
});
