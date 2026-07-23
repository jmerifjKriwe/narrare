"use client";

/**
 * DialogueCoachPanel — flagship AI-assist side panel (ASSIST-004).
 *
 * Shell + composition root for the Dialogue Coach. Composes
 * {@link ./_components/DialogueModeSelector} (the two primary actions) and
 * {@link ./_components/DialogueIssueList} (issues → cards → alternatives).
 *
 * Design decisions (deviations from the plan's verbatim panel, each forced by
 * the verbatim TEST behaviour — see the task report):
 *  - Mode selection IS the run trigger. The verbatim test clicks a mode button
 *    and expects a run; `patterns-explicit-variants` makes the two mode
 *    buttons the two primary actions, so there is no redundant separate
 *    "Run" button.
 *  - Full dotted i18n keys (`dialogueCoach.*`) via the root namespace, so they
 *    resolve under the global next-intl test mock (which returns keys verbatim)
 *    AND in production.
 *
 * Lifecycle runs through {@link useDialogueCoach} → `useAIOperation` (ADR-043):
 * no manual AbortController. Layout mirrors the sibling analysis panels
 * (CharacterVoicePanel / VoiceCheckPanel: 400px, border-left, violet accent).
 *
 * @module DialogueCoachPanel
 */
import type { Editor } from "@tiptap/react";
import { ArrowLeft, MessagesSquare, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import { useDialogueCoach } from "@/lib/hooks/useDialogueCoach";
import type { DialogueCoachMode } from "@/types";
import { DialogueIssueList } from "./_components/DialogueIssueList";
import { DialogueModeSelector } from "./_components/DialogueModeSelector";

interface DialogueCoachPanelProps {
  chapterId: string;
  /** Current editor text selection (null = nothing selected). */
  selectionText: string | null;
  editor: Editor;
  onClose: () => void;
}

export function DialogueCoachPanel({
  chapterId,
  selectionText,
  editor,
  onClose,
}: DialogueCoachPanelProps) {
  const t = useTranslations();
  const [mode, setMode] = useState<DialogueCoachMode>("analyze");
  const { result, error, progress, run, isLoading, isStreaming, isComplete, isError } =
    useDialogueCoach();

  const inFlight = isLoading || isStreaming;
  const hasSelection = !!selectionText && selectionText.trim().length > 0;

  /**
   * Selecting a mode is the primary action: it stages the mode and — when a
   * selection exists — immediately runs the coach with that mode. With no
   * selection the buttons are disabled, so `selectionText!` is safe here.
   */
  const handleSelectMode = useCallback(
    (next: DialogueCoachMode) => {
      setMode(next);
      if (selectionText) {
        run({ chapterId, selectionText, mode: next });
      }
    },
    [chapterId, selectionText, run],
  );

  /** After an alternative is applied, keep the panel open for further review. */
  const handleApplied = useCallback(() => {
    /* no-op: the editor mutation already landed; panel stays open */
  }, []);

  return (
    <div className="flex flex-col h-full border-l border-border bg-background w-[400px] min-w-[400px]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={t("dialogueCoach.close")}
          >
            <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <MessagesSquare className="w-5 h-5 text-violet-500 flex-shrink-0" aria-hidden="true" />
            <h3 className="font-medium truncate">{t("dialogueCoach.title")}</h3>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={t("dialogueCoach.close")}
        >
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>

      {/* Controls — the two mode buttons are the primary run actions. */}
      <div className="px-4 py-3 border-b border-border bg-muted/30 space-y-2">
        <DialogueModeSelector
          mode={mode}
          onSelect={handleSelectMode}
          disabled={inFlight || !hasSelection}
        />
        {!hasSelection && (
          <p className="text-xs text-muted-foreground">{t("dialogueCoach.selectPrompt")}</p>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-4 space-y-4">
          {inFlight && (
            <p className="text-sm text-muted-foreground" role="status" aria-live="polite">
              {progress ?? t("dialogueCoach.analyzing")}
            </p>
          )}
          {isError && (
            <div className="text-sm text-destructive" role="alert">
              {error?.userMessage ?? t("dialogueCoach.failed")}
            </div>
          )}
          {isComplete && result && (
            <section aria-live="polite" className="space-y-3">
              {result.adaptive_summary && (
                <p className="text-xs text-muted-foreground border border-border rounded-md p-2">
                  {result.adaptive_summary}
                </p>
              )}
              <DialogueIssueList issues={result.issues} editor={editor} onApplied={handleApplied} />
            </section>
          )}
          {/* Idle with a selection but no run yet — nudge toward the modes. */}
          {!inFlight && !isError && !isComplete && hasSelection && (
            <p className="text-sm text-muted-foreground text-center py-8">
              {t("dialogueCoach.idleHint")}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
