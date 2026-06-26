"use client";

/**
 * CoreferenceTrigger — toolbar button that opens the CoreferencePanel.
 *
 * Renders as an icon + text button in the editor toolbar.
 * Uses i18n for the label and tooltip.
 * Follows POVTrigger pattern exactly.
 */

import { Users } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEditorStore } from "@/lib/stores/editorStore";

interface CoreferenceTriggerProps {
  /** Whether a chapter is active (disabled if null). */
  disabled?: boolean;
}

export function CoreferenceTrigger({ disabled = false }: CoreferenceTriggerProps) {
  const t = useTranslations("analysis");
  const coreferencePanelOpen = useEditorStore((s) => s.coreferencePanelOpen);
  const toggleCoreferencePanel = useEditorStore((s) => s.toggleCoreferencePanel);

  return (
    <button
      type="button"
      onClick={toggleCoreferencePanel}
      disabled={disabled}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded hover:bg-accent transition-colors text-sm text-sky-600 dark:text-sky-400 ${
        coreferencePanelOpen ? "bg-accent" : ""
      } disabled:opacity-50`}
      title={t("coreference.triggerTooltip")}
      aria-label={t("coreference.triggerTooltip")}
      aria-pressed={coreferencePanelOpen}
    >
      <Users className="w-3.5 h-3.5" />
      <span>{t("coreference.trigger")}</span>
    </button>
  );
}
