"use client";

/**
 * AuthorVoiceTrigger — toolbar button that opens the AuthorVoicePanel.
 *
 * Renders as an icon + text button in the editor toolbar. Uses i18n for the
 * label and tooltip. Follows the VoiceDriftTrigger pattern (store-coupled
 * panel toggle, reflects the active state) — author voice is the novel-scoped
 * sibling of voice drift (both on-demand whole-novel profiling panels).
 *
 * @module AuthorVoiceTrigger
 */

import { PenLine } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";

export function AuthorVoiceTrigger() {
  const t = useTranslations("analysis");
  const activeRightPanel = useEditorStore((s) => s.rightPanel.active);
  const toggleRightPanel = useEditorStore((s) => s.toggleRightPanel);
  const isAuthorVoiceActive = activeRightPanel === "author_voice";

  return (
    <button
      type="button"
      onClick={() => toggleRightPanel("author_voice", "toolbar")}
      className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-sm text-violet-600 transition-colors hover:bg-accent dark:text-violet-400 ${
        isAuthorVoiceActive ? "bg-accent" : ""
      }`}
      title={t("authorVoice.triggerTooltip")}
      aria-label={t("authorVoice.triggerTooltip")}
      aria-pressed={isAuthorVoiceActive}
    >
      <PenLine className="h-3.5 w-3.5" />
      <span>{t("authorVoice.trigger")}</span>
    </button>
  );
}
