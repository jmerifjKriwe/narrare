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
  const activeRightPanel = useEditorStore((s) => s.rightPanel.active);
  const toggleRightPanel = useEditorStore((s) => s.toggleRightPanel);
  const isBetaReaderActive = activeRightPanel === "beta_reader";

  return (
    <button
      type="button"
      onClick={() => toggleRightPanel("beta_reader", "toolbar")}
      disabled={disabled}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-primary ${
        isBetaReaderActive ? "bg-accent" : ""
      } disabled:opacity-50`}
      title={t("triggerTooltip")}
      aria-label={t("triggerTooltip")}
      aria-pressed={isBetaReaderActive}
    >
      <BookOpen className="w-3.5 h-3.5" />
      <span>{t("trigger")}</span>
    </button>
  );
}
