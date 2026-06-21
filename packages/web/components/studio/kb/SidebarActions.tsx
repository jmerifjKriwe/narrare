"use client";

/**
 * SidebarActions — Bottom action buttons for the KB Category Sidebar.
 *
 * Extracted from KBCategorySidebar for RULE-04 compliance.
 */

import { ShieldCheck, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";

interface SidebarActionsProps {
  onAnalyze?: () => void;
  onConsistencyCheck?: () => void;
}

export function SidebarActions({ onAnalyze, onConsistencyCheck }: SidebarActionsProps) {
  const t = useTranslations("studio");

  if (!onAnalyze && !onConsistencyCheck) return null;

  return (
    <div className="p-2 border-t border-border space-y-1.5">
      {onAnalyze && (
        <button
          type="button"
          onClick={onAnalyze}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-md bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400 hover:bg-purple-100 dark:hover:bg-purple-900/30 transition-colors text-sm font-medium"
        >
          <Sparkles className="w-4 h-4" />
          {t("worldbuilding.analyzeButton")}
        </button>
      )}
      {onConsistencyCheck && (
        <button
          type="button"
          onClick={onConsistencyCheck}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-md bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-900/30 transition-colors text-sm font-medium"
        >
          <ShieldCheck className="w-4 h-4" />
          {t("consistency.checkButton")}
        </button>
      )}
    </div>
  );
}
