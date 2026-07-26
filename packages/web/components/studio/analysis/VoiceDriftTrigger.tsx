"use client";

/**
 * VoiceDriftTrigger — toolbar button that opens the VoiceDriftPanel.
 *
 * Renders as an icon + text button in the editor toolbar. Uses i18n for the
 * label and tooltip. Follows the CharacterVoiceTrigger pattern (store-coupled
 * panel toggle, reflects the active state).
 *
 * @module VoiceDriftTrigger
 */

import { Waves } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";

export function VoiceDriftTrigger() {
  const t = useTranslations("analysis");
  const activeRightPanel = useEditorStore((s) => s.rightPanel.active);
  const toggleRightPanel = useEditorStore((s) => s.toggleRightPanel);
  const isVoiceDriftActive = activeRightPanel === "voice_drift";

  return (
    <button
      type="button"
      onClick={() => toggleRightPanel("voice_drift", "toolbar")}
      className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-sm text-violet-600 transition-colors hover:bg-accent dark:text-violet-400 ${
        isVoiceDriftActive ? "bg-accent" : ""
      }`}
      title={t("voiceDrift.triggerTooltip")}
      aria-label={t("voiceDrift.triggerTooltip")}
      aria-pressed={isVoiceDriftActive}
    >
      <Waves className="h-3.5 w-3.5" />
      <span>{t("voiceDrift.trigger")}</span>
    </button>
  );
}
