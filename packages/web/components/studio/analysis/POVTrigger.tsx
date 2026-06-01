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
  const povPanelOpen = useEditorStore((s) => s.povPanelOpen);
  const togglePovPanel = useEditorStore((s) => s.togglePovPanel);

  return (
    <button
      type="button"
      onClick={togglePovPanel}
      disabled={disabled}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-purple-600 dark:text-purple-400 ${
        povPanelOpen ? "bg-accent" : ""
      } disabled:opacity-50`}
      title={t("pov.triggerTooltip")}
      aria-label={t("pov.triggerTooltip")}
      aria-pressed={povPanelOpen}
    >
      <Eye className="w-3.5 h-3.5" />
      <span>{t("pov.trigger")}</span>
    </button>
  );
}
