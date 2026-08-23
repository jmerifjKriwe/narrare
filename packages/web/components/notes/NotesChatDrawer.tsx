"use client";

/**
 * NotesChatDrawer — right-side slide-over hosting ChatPanel for a note
 * (NOTES-001 §7 "discuss in chat"). Works for global notes (projectId null)
 * and linked notes (projectId = note.novel_id) alike.
 */

import { StickyNote, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
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

  if (!note) return null;

  const bannerTitle = noteDisplayTitle(note) || t("list.untitled");

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            variants={overlayVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
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
                aria-label={t("editor.discuss")}
                className="shrink-0 cursor-pointer rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                onClick={onClose}
              >
                <X className="size-4" />
              </button>
            </header>
            <div className="min-h-0 flex-1">
              <ChatPanel
                projectId={note.novel_id}
                noteId={note.id}
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
