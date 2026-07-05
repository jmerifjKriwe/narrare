"use client";

/**
 * ConsistencyTrigger — toolbar button that opens the ConsistencyPanel.
 *
 * Renders as an icon + text button in the editor toolbar via the shared
 * ToolbarButton primitive. Uses i18n for the label. Follows the
 * BetaReaderTrigger pattern.
 */

import { Shield } from "lucide-react";
import { useTranslations } from "next-intl";
import { ToolbarButton } from "@/components/ui/toolbar-button";
import { useEditorStore } from "@/lib/stores/editorStore";

interface ConsistencyTriggerProps {
  /** Whether a chapter is active (disabled if null). */
  readonly disabled?: boolean;
}

export function ConsistencyTrigger({ disabled = false }: ConsistencyTriggerProps) {
  const t = useTranslations("analysis");
  const activeRightPanel = useEditorStore((s) => s.rightPanel.active);
  const toggleRightPanel = useEditorStore((s) => s.toggleRightPanel);
  const isConsistencyActive = activeRightPanel === "consistency";

  return (
    <ToolbarButton
      label={t("consistency.trigger")}
      icon={Shield}
      showLabel
      active={isConsistencyActive}
      disabled={disabled}
      onClick={() => toggleRightPanel("consistency", "toolbar")}
    />
  );
}
