"use client";

/**
 * NotesChatDrawer — right-side slide-over hosting ChatPanel for a note
 * (NOTES-001 §7 "discuss in chat"). Works for global notes (projectId null)
 * and linked notes (projectId = note.novel_id) alike.
 *
 * Drawer-owned lifecycle (follow-up P-FE4 — dismissal no longer relies on
 * ChatPanel's window listener):
 * - Escape closes the drawer via this component's OWN window listener.
 * - When the discussed note vanishes while the drawer is open (deleted,
 *   filtered out), the last known note is kept in state so the drawer stays
 *   renderable through the AnimatePresence exit animation (no blank flash);
 *   the drawer then closes itself via onClose.
 *
 * Note-context v1 decision (final-review record, NOTES-001 §6b): `note_id`
 * is sent on EVERY turn of a drawer conversation — the note block is
 * re-embedded per message and persists in the stored history. The per-turn
 * token growth is accepted for v1; revisit if drawer conversations grow
 * long enough for context bloat to matter.
 */

import { StickyNote, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { ChatPanel } from "@/components/studio/editor/ChatPanel";
import { overlayVariants, panelSlideRightVariants } from "@/lib/motion-variants";
import { type Note, noteDisplayTitle } from "@/types";

export interface NotesChatDrawerProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly note: Note | null;
}

export function NotesChatDrawer({ open, onClose, note }: NotesChatDrawerProps) {
  const t = useTranslations("notes");

  // Last known non-null note: keeps the banner (and ChatPanel context)
  // renderable during the exit phase after the note vanished.
  const [lastNote, setLastNote] = useState<Note | null>(note);
  useEffect(() => {
    if (note) setLastNote(note);
  }, [note]);
  const shownNote = note ?? lastNote;

  // A vanished discussed note closes the drawer via onClose; lastNote keeps
  // the exit animation alive through the unmount transition.
  useEffect(() => {
    if (open && note === null) onClose();
  }, [open, note, onClose]);

  // Drawer-owned Escape dismissal, independent of ChatPanel's listener.
  // (Both are window-level: while a response streams, ChatPanel's handler
  // still cancels the stream first — registered earlier on mount.)
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  const bannerTitle = shownNote ? noteDisplayTitle(shownNote) || t("list.untitled") : "";

  return (
    <AnimatePresence>
      {open && shownNote && (
        <>
          <motion.div
            variants={overlayVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            data-testid="note-chat-overlay"
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.aside
            variants={panelSlideRightVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            role="dialog"
            aria-modal="true"
            aria-label={t("editor.discuss")}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col overflow-hidden border-l border-border bg-card shadow-2xl"
          >
            <header className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-4 py-3">
              <p
                data-testid="note-chat-banner"
                className="flex min-w-0 items-center gap-2 text-sm text-muted-foreground"
              >
                <StickyNote className="size-4 shrink-0 text-primary" />
                <span className="truncate">{t("chat.attachedNote", { title: bannerTitle })}</span>
              </p>
              <button
                type="button"
                data-testid="note-chat-close"
                aria-label={t("chat.close")}
                className="shrink-0 cursor-pointer rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                onClick={onClose}
              >
                <X className="size-4" />
              </button>
            </header>
            <div className="min-h-0 flex-1">
              <ChatPanel
                projectId={shownNote.novel_id}
                noteId={shownNote.id}
                onClose={onClose}
                className="w-full border-l-0"
              />
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
