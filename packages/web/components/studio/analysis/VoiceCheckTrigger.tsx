"use client";

/**
 * VoiceCheckTrigger — on-demand "Check Voice" run button (WRITE-010).
 *
 * Renders as an icon + text button. Unlike the character-voice trigger (a
 * store-coupled panel toggle), this is the action button that RUNS the voice
 * consistency check: it is props-driven (controlled by the owning panel) and
 * is disabled-while-loading with an inline spinner + `aria-busy`.
 *
 * Page/store wiring (mounting this in the toolbar) is a separate step (4c);
 * this component is intentionally controlled via props so it stays decoupled
 * from the editor store and is fully testable in isolation.
 *
 * Uses i18n for the label, tooltip, and aria-label. Follows the
 * CharacterVoiceTrigger visual pattern.
 */

import { BadgeCheck, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";

interface VoiceCheckTriggerProps {
  /** Run the voice-check analysis when clicked. */
  onClick: () => void;
  /** Hard-disable the button (e.g. when no chapter is active). */
  disabled?: boolean;
  /** While a run is in-flight: disables the button and shows a spinner. */
  isLoading?: boolean;
}

export function VoiceCheckTrigger({
  onClick,
  disabled = false,
  isLoading = false,
}: VoiceCheckTriggerProps) {
  const t = useTranslations("analysis");
  const isDisabled = disabled || isLoading;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isDisabled}
      aria-busy={isLoading}
      className="flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-violet-600 dark:text-violet-400 disabled:opacity-50 disabled:cursor-not-allowed"
      title={t("voiceCheck.triggerTooltip")}
      aria-label={t("voiceCheck.triggerAriaLabel")}
    >
      {isLoading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : (
        <BadgeCheck className="w-3.5 h-3.5" />
      )}
      <span>{t("voiceCheck.trigger")}</span>
    </button>
  );
}
