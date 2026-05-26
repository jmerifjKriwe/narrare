"use client";

/**
 * BetaReaderTrigger — toolbar button that opens the BetaReaderPanel.
 *
 * Renders as an icon + text button in the editor toolbar.
 * Uses i18n for the label and tooltip.
 */

import { BookOpen } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";

interface BetaReaderTriggerProps {
  /** Whether a chapter is active (disabled if null). */
  disabled?: boolean;
}

export function BetaReaderTrigger({ disabled = false }: BetaReaderTriggerProps) {
  const t = useTranslations("analysis");
  const betaReaderPanelOpen = useEditorStore((s) => s.betaReaderPanelOpen);
  const toggleBetaReaderPanel = useEditorStore((s) => s.toggleBetaReaderPanel);

  return (
    <button
      type="button"
      onClick={toggleBetaReaderPanel}
      disabled={disabled}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-primary ${
        betaReaderPanelOpen ? "bg-accent" : ""
      } disabled:opacity-50`}
      title={t("triggerTooltip")}
      aria-label={t("triggerTooltip")}
      aria-pressed={betaReaderPanelOpen}
    >
      <BookOpen className="w-3.5 h-3.5" />
      <span>{t("trigger")}</span>
    </button>
  );
}
