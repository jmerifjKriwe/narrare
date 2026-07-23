"use client";

/**
 * DialogueModeSelector — the two primary actions of the Dialogue Coach.
 *
 * Per `vercel-composition-patterns` (`patterns-explicit-variants`): the two
 * modes are exposed as two EXPLICIT controls, never a `mode?: "analyze" |
 * "improve"` boolean-style prop on the panel. Selecting a mode is the primary
 * action surface — see {@link ../DialogueCoachPanel}, where `onSelect` both
 * stages the mode and kicks off the run (the modes ARE the run triggers).
 *
 * Accessibility: a `<fieldset>`/`<legend>` labelled group of toggle buttons
 * using `aria-pressed` — each button is independently activatable and
 * communicates its selected state to assistive tech.
 *
 * i18n keys are full dotted (`dialogueCoach.mode.*`) so they resolve both in
 * production (root namespace) and under the global next-intl test mock.
 *
 * @module DialogueModeSelector
 */
import { useTranslations } from "next-intl";
import type { DialogueCoachMode } from "@/types";

interface DialogueModeSelectorProps {
  mode: DialogueCoachMode;
  onSelect: (mode: DialogueCoachMode) => void;
  disabled: boolean;
}

/** The two coach modes, in display order. */
const MODE_OPTIONS: readonly DialogueCoachMode[] = ["analyze", "improve"] as const;

export function DialogueModeSelector({ mode, onSelect, disabled }: DialogueModeSelectorProps) {
  const t = useTranslations();
  return (
    <fieldset className="flex gap-2 border-0 p-0 m-0">
      <legend className="sr-only">{t("dialogueCoach.mode.groupLabel")}</legend>
      {MODE_OPTIONS.map((opt) => {
        const active = mode === opt;
        return (
          <button
            key={opt}
            type="button"
            onClick={() => onSelect(opt)}
            disabled={disabled}
            aria-pressed={active}
            className={`flex-1 px-3 py-1.5 text-sm font-medium rounded-md border transition-colors ${
              active
                ? "bg-primary text-primary-foreground border-primary shadow-sm"
                : "border-border text-foreground hover:bg-muted"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {t(`dialogueCoach.mode.${opt}`)}
          </button>
        );
      })}
    </fieldset>
  );
}
