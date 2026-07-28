"use client";

/**
 * AuthorVoiceDriftTrigger — toolbar button that opens the AuthorVoiceDriftPanel.
 *
 * Renders as an icon + text button in the editor toolbar. Uses i18n for the
 * label and tooltip. Follows the AuthorVoiceTrigger / VoiceDriftTrigger pattern
 * (store-coupled panel toggle, reflects the active state) — author-voice-drift
 * is the novel-scoped narrator-drift sibling of character voice drift.
 *
 * @module AuthorVoiceDriftTrigger
 */

import { Activity } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";

export function AuthorVoiceDriftTrigger() {
  const t = useTranslations("analysis");
  const activeRightPanel = useEditorStore((s) => s.rightPanel.active);
  const toggleRightPanel = useEditorStore((s) => s.toggleRightPanel);
  const isAuthorVoiceDriftActive = activeRightPanel === "author_voice_drift";

  return (
    <button
      type="button"
      onClick={() => toggleRightPanel("author_voice_drift", "toolbar")}
      className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-sm text-violet-600 transition-colors hover:bg-accent dark:text-violet-400 ${
        isAuthorVoiceDriftActive ? "bg-accent" : ""
      }`}
      title={t("authorVoiceDrift.triggerTooltip")}
      aria-label={t("authorVoiceDrift.triggerTooltip")}
      aria-pressed={isAuthorVoiceDriftActive}
    >
      <Activity className="h-3.5 w-3.5" />
      <span>{t("authorVoiceDrift.trigger")}</span>
    </button>
  );
}
