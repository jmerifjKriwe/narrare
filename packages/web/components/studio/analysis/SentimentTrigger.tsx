"use client";

/**
 * SentimentTrigger — toolbar button that opens the SentimentPanel.
 *
 * Renders as an icon + text button in the editor toolbar.
 * Uses i18n for the label and tooltip.
 * Follows BetaReaderTrigger pattern exactly.
 */

import { TrendingUp } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";

interface SentimentTriggerProps {
  /** Whether a chapter is active (disabled if null). */
  disabled?: boolean;
}

export function SentimentTrigger({ disabled = false }: SentimentTriggerProps) {
  const t = useTranslations("analysis");
  const sentimentPanelOpen = useEditorStore((s) => s.sentimentPanelOpen);
  const toggleSentimentPanel = useEditorStore((s) => s.toggleSentimentPanel);

  return (
    <button
      type="button"
      onClick={toggleSentimentPanel}
      disabled={disabled}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-blue-600 dark:text-blue-400 ${
        sentimentPanelOpen ? "bg-accent" : ""
      } disabled:opacity-50`}
      title={t("sentiment.triggerTooltip")}
      aria-label={t("sentiment.triggerTooltip")}
      aria-pressed={sentimentPanelOpen}
    >
      <TrendingUp className="w-3.5 h-3.5" />
      <span>{t("sentiment.trigger")}</span>
    </button>
  );
}
