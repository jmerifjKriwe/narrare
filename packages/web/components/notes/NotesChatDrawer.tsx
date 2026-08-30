"use client";

/**
 * NotesChatDrawer — right-side slide-over hosting ChatPanel for a note
 * (NOTES-001 §7 "discuss in chat"). Works for global notes (projectId null)
 * and linked notes (projectId = note.novel_id) alike.
 *
 * Drawer-owned lifecycle:
 * - Escape dismissal is DELEGATED to ChatPanel's window listener (single
 *   owner — see the comment above the ChatPanel mount). P-FE4 originally
 *   added a drawer-owned listener for dismissal independence; follow-up
 *   P-DRAWER removed it again because ChatPanel is mounted in EVERY frame
 *   where the drawer renders visible content, making the drawer listener
 *   only ever a SECOND one: Escape while idle fired onClose twice, and
 *   Escape while streaming closed the drawer on top of ChatPanel's
 *   deliberate cancel-first semantics.
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
import { useEffect, useRef, useState } from "react";
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

  // Initial dialog focus (follow-up b3): move focus INTO the dialog when it
  // opens so screen readers announce it and Tab starts inside the overlay —
  // the container-focus variant of the WAI-ARIA dialog pattern. Deliberately
  // NOT useDialogFocus: it owns Escape and the focus trap, which would
  // collide with ChatPanel's window Escape listener (single-owner rule,
  // follow-up P-DRAWER). This adds no listener. Refocusing the chat INPUT
  // after a stream completes is NOT reachable from here — ChatPanel keeps
  // isStreaming and its input ref internal (see follow-up b3 report).
  const asideRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (open) asideRef.current?.focus();
  }, [open]);

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
            ref={asideRef}
            variants={panelSlideRightVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            role="dialog"
            aria-modal="true"
            aria-label={t("editor.discuss")}
            tabIndex={-1}
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
              {/* Escape ownership (follow-up P-DRAWER): ChatPanel is mounted
                  in every frame where this drawer renders visible content
                  (the whole aside is gated on `open && shownNote`), and its
                  window-level Escape listener covers both states deliberately
                  (cancel-while-streaming, close-otherwise, wired to this
                  drawer's onClose below). The drawer therefore adds NO second
                  listener — one Escape owner per surface, like
                  CoAuthorReviewPhase delegating to CoAuthorPanel. The only
                  open-but-invisible state (note AND lastNote null) renders
                  nothing and is auto-closed by the vanished-note effect
                  above, so no visible frame lacks Escape coverage. The
                  exactly-once close is pinned by NotesChatDrawer
                  .composition.test.tsx with the REAL ChatPanel. */}
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
