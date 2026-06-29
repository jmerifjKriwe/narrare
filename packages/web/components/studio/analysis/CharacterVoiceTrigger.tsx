"use client";

/**
 * CharacterVoiceTrigger — toolbar button that opens the CharacterVoicePanel.
 *
 * Renders as an icon + text button in the editor toolbar.
 * Uses i18n for the label and tooltip. Follows the CoreferenceTrigger pattern.
 */

import { AudioLines } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";

interface CharacterVoiceTriggerProps {
  /** Whether a chapter is active (disabled if null). */
  disabled?: boolean;
}

export function CharacterVoiceTrigger({ disabled = false }: CharacterVoiceTriggerProps) {
  const t = useTranslations("analysis");
  const characterVoicePanelOpen = useEditorStore((s) => s.characterVoicePanelOpen);
  const toggleCharacterVoicePanel = useEditorStore((s) => s.toggleCharacterVoicePanel);

  return (
    <button
      type="button"
      onClick={toggleCharacterVoicePanel}
      disabled={disabled}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-violet-600 dark:text-violet-400 ${
        characterVoicePanelOpen ? "bg-accent" : ""
      } disabled:opacity-50`}
      title={t("characterVoice.triggerTooltip")}
      aria-label={t("characterVoice.triggerTooltip")}
      aria-pressed={characterVoicePanelOpen}
    >
      <AudioLines className="w-3.5 h-3.5" />
      <span>{t("characterVoice.trigger")}</span>
    </button>
  );
}
