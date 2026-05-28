"use client";

/**
 * ConsistencyTrigger — toolbar button that opens the ConsistencyPanel.
 *
 * Renders as an icon + text button in the editor toolbar.
 * Uses i18n for the label and tooltip.
 * Follows BetaReaderTrigger pattern exactly.
 */

import { Shield } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";

interface ConsistencyTriggerProps {
  /** Whether a chapter is active (disabled if null). */
  disabled?: boolean;
}

export function ConsistencyTrigger({ disabled = false }: ConsistencyTriggerProps) {
  const t = useTranslations("analysis");
  const consistencyPanelOpen = useEditorStore((s) => s.consistencyPanelOpen);
  const toggleConsistencyPanel = useEditorStore((s) => s.toggleConsistencyPanel);

  return (
    <button
      type="button"
      onClick={toggleConsistencyPanel}
      disabled={disabled}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-green-600 dark:text-green-400 ${
        consistencyPanelOpen ? "bg-accent" : ""
      } disabled:opacity-50`}
      title={t("consistency.triggerTooltip")}
      aria-label={t("consistency.triggerTooltip")}
      aria-pressed={consistencyPanelOpen}
    >
      <Shield className="w-3.5 h-3.5" />
      <span>{t("consistency.trigger")}</span>
    </button>
  );
}
