"use client";

/**
 * ReadabilityTrigger — toolbar button that opens the ReadabilityPanel.
 *
 * Renders as an icon + text button in the editor toolbar.
 * Uses i18n for the label and tooltip.
 * Follows SentimentTrigger pattern exactly.
 */

import { BookOpen } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";

interface ReadabilityTriggerProps {
  /** Whether a chapter is active (disabled if null). */
  disabled?: boolean;
}

export function ReadabilityTrigger({ disabled = false }: ReadabilityTriggerProps) {
  const t = useTranslations("analysis");
  const readabilityPanelOpen = useEditorStore((s) => s.readabilityPanelOpen);
  const toggleReadabilityPanel = useEditorStore((s) => s.toggleReadabilityPanel);

  return (
    <button
      type="button"
      onClick={toggleReadabilityPanel}
      disabled={disabled}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-orange-600 dark:text-orange-400 ${
        readabilityPanelOpen ? "bg-accent" : ""
      } disabled:opacity-50`}
      title={t("readability.triggerTooltip")}
      aria-label={t("readability.triggerTooltip")}
      aria-pressed={readabilityPanelOpen}
    >
      <BookOpen className="w-3.5 h-3.5" />
      <span>{t("readability.trigger")}</span>
    </button>
  );
}
