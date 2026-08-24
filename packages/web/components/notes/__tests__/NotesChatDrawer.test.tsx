/**
 * NotesChatDrawer tests (NOTES-001 §6b/§7): renders the chat surface for a
 * (possibly global) note, with the attached-note banner and close handling.
 * ChatPanel is mocked to a stub — its internals are covered by the existing
 * editor chat tests; this file asserts drawer composition (banner, close,
 * overlay click, Escape, vanished-note exit behavior), including the
 * drawer's OWN Escape handler in isolation (follow-up P-FE4: dismissal no
 * longer relies on ChatPanel's window listener).
 *
 * next-intl is mocked LOCALLY (overriding the centralized setupTests mock,
 * which returns i18n keys verbatim): the banner assertions require real
 * message templates with {title} interpolation. Same pattern as
 * ChatPanel.error.test.tsx.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Note } from "@/types";
import { NotesChatDrawer } from "../NotesChatDrawer";

vi.mock("@/components/studio/editor/ChatPanel", () => ({
  ChatPanel: () => <div data-testid="chat-panel-stub" />,
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    const translations: Record<string, string> = {
      "chat.attachedNote": "Discussing note: {title}",
      "chat.close": "Close chat",
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
    // a11y: the X closes the drawer — its label must say so, not repeat the
    // dialog's "discuss" title (final review).
    expect(screen.getByTestId("note-chat-close")).toHaveAccessibleName("Close chat");
    fireEvent.click(screen.getByTestId("note-chat-close"));
    expect(onClose).toHaveBeenCalled();
  });

  it("closes via its own Escape handler, not ChatPanel's (follow-up P-FE4)", () => {
    const onClose = vi.fn();
    render(<NotesChatDrawer open onClose={onClose} note={note} />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not listen for Escape while closed", () => {
    const onClose = vi.fn();
    render(<NotesChatDrawer open={false} onClose={onClose} note={note} />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes when the overlay is clicked", () => {
    const onClose = vi.fn();
    render(<NotesChatDrawer open onClose={onClose} note={note} />);
    fireEvent.click(screen.getByTestId("note-chat-overlay"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes itself and keeps the last note visible when the discussed note vanishes", () => {
    const onClose = vi.fn();
    const { rerender } = render(<NotesChatDrawer open onClose={onClose} note={note} />);
    rerender(<NotesChatDrawer open onClose={onClose} note={null} />);
    // The drawer reports its own dismissal…
    expect(onClose).toHaveBeenCalledTimes(1);
    // …and the banner still renders the LAST known note, so the exit
    // animation never shows a blank drawer mid-transition.
    expect(screen.getByTestId("note-chat-banner")).toHaveTextContent("Twist");
  });
});
