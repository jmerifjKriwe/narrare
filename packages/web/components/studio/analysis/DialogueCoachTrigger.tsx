"use client";

/**
 * DialogueCoachTrigger — toolbar button that opens the DialogueCoachPanel
 * (ASSIST-004, ADR-069 Decision 16: a sibling in the analysis panel family).
 *
 * Mirrors {@link CharacterVoiceTrigger}: subscribes to the *derived* panel
 * state (`rightPanel.active === "dialogue_coach"`) rather than the whole store
 * (vercel-composition-patterns: pull only the slice each component needs), and
 * toggles via `toggleRightPanel`. Uses the root next-intl namespace with full
 * dotted `dialogueCoach.*` keys so labels resolve both under the global test
 * mock (returns keys verbatim) and in production — matching DialogueCoachPanel.
 */
import { MessagesSquare } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";

interface DialogueCoachTriggerProps {
  /** Whether a chapter is active (disabled if null). */
  disabled?: boolean;
}

export function DialogueCoachTrigger({ disabled = false }: DialogueCoachTriggerProps) {
  const t = useTranslations();
  const activeRightPanel = useEditorStore((s) => s.rightPanel.active);
  const toggleRightPanel = useEditorStore((s) => s.toggleRightPanel);
  const isActive = activeRightPanel === "dialogue_coach";

  return (
    <button
      type="button"
      onClick={() => toggleRightPanel("dialogue_coach", "toolbar")}
      disabled={disabled}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-violet-600 dark:text-violet-400 ${
        isActive ? "bg-accent" : ""
      } disabled:opacity-50`}
      title={t("dialogueCoach.triggerTooltip")}
      aria-label={t("dialogueCoach.triggerTooltip")}
      aria-pressed={isActive}
    >
      <MessagesSquare className="w-3.5 h-3.5" />
      <span>{t("dialogueCoach.trigger")}</span>
    </button>
  );
}
