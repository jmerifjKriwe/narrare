"use client";

/**
 * POVTrigger — toolbar button that opens the POVPanel.
 *
 * Renders as an icon + text button in the editor toolbar.
 * Uses i18n for the label and tooltip.
 * Follows SentimentTrigger pattern exactly.
 */

import { Eye } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";

interface POVTriggerProps {
  /** Whether a chapter is active (disabled if null). */
  disabled?: boolean;
}

export function POVTrigger({ disabled = false }: POVTriggerProps) {
  const t = useTranslations("analysis");
  const activeRightPanel = useEditorStore((s) => s.rightPanel.active);
  const toggleRightPanel = useEditorStore((s) => s.toggleRightPanel);
  const isPovActive = activeRightPanel === "pov";

  return (
    <button
      type="button"
      onClick={() => toggleRightPanel("pov", "toolbar")}
      disabled={disabled}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-purple-600 dark:text-purple-400 ${
        isPovActive ? "bg-accent" : ""
      } disabled:opacity-50`}
      title={t("pov.triggerTooltip")}
      aria-label={t("pov.triggerTooltip")}
      aria-pressed={isPovActive}
    >
      <Eye className="w-3.5 h-3.5" />
      <span>{t("pov.trigger")}</span>
    </button>
  );
}
