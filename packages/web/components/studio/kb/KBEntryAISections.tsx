"use client";

/**
 * KBEntryAISections — Wiki summary and AI improve panel for KB entry detail.
 *
 * Extracted from KBEntryDetail for RULE-04 compliance.
 */

import { Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { KBImprovePanel } from "./KBImprovePanel";
import { WikiSummaryPanel } from "./WikiSummaryPanel";

interface KBEntryAISectionsProps {
  novelId: string;
  entryId: string;
  entryName: string;
  entityType: string;
}

export function KBEntryAISections({
  novelId,
  entryId,
  entryName,
  entityType,
}: KBEntryAISectionsProps) {
  const t = useTranslations("studio");
  const [showImprovePanel, setShowImprovePanel] = useState(false);

  return (
    <>
      {/* AI Wiki Summary */}
      <WikiSummaryPanel
        novelId={novelId}
        entityId={entryId}
        entityName={entryName}
        entityType={entityType}
      />

      {/* AI Improve section */}
      <div className="pt-4 border-t border-border/50">
        {showImprovePanel ? (
          <KBImprovePanel
            novelId={novelId}
            entryId={entryId}
            onClose={() => setShowImprovePanel(false)}
            onApplied={() => setShowImprovePanel(false)}
          />
        ) : (
          <button
            type="button"
            onClick={() => setShowImprovePanel(true)}
            className="flex items-center gap-2 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
          >
            <Sparkles className="w-4 h-4 text-purple-500" />
            {t("kb.improveWithAI")}
          </button>
        )}
      </div>
    </>
  );
}
