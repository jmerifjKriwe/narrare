"use client";

/**
 * ExtractionReview — Results list with bulk actions, item cards,
 * and collapsible analysis notes.
 *
 * Follows KBEnhanceReview bulk select pattern.
 */

import { ChevronDown, ChevronUp } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { ExtractionItem } from "@/lib/api/extraction";
import { ExtractionItemCard } from "./ExtractionItemCard";

interface ExtractionReviewProps {
  items: ExtractionItem[];
  selectedIndices: Set<number>;
  onToggleItem: (index: number) => void;
  onSelectAll: () => void;
  onSelectNone: () => void;
  analysisNotes: string;
}

export function ExtractionReview({
  items,
  selectedIndices,
  onToggleItem,
  onSelectAll,
  onSelectNone,
  analysisNotes,
}: ExtractionReviewProps) {
  const t = useTranslations("studio");
  const [notesExpanded, setNotesExpanded] = useState(false);

  return (
    <div className="space-y-4">
      {/* Bulk actions bar */}
      <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
        <span className="text-sm text-muted-foreground">
          {t("kb.extractionResultsSummary", { count: items.length })}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onSelectAll}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            {t("kb.extractionSelectAll")}
          </button>
          <span className="text-muted-foreground">|</span>
          <button
            type="button"
            onClick={onSelectNone}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            {t("kb.extractionSelectNone")}
          </button>
        </div>
      </div>

      {/* Item cards */}
      <div className="space-y-3">
        {items.map((item, idx) => (
          <ExtractionItemCard
            key={`${item.item_type}-${item.name}-${item.confidence}-${item.source_text.slice(0, 20)}`}
            item={item}
            isSelected={selectedIndices.has(idx)}
            onToggle={() => onToggleItem(idx)}
          />
        ))}
      </div>

      {/* Analysis notes (collapsible) */}
      {analysisNotes && (
        <div className="border border-border rounded-lg overflow-hidden">
          <button
            type="button"
            onClick={() => setNotesExpanded((prev) => !prev)}
            className="w-full flex items-center justify-between p-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
          >
            <span className="text-sm font-medium text-muted-foreground">
              {t("kb.extractionAnalysisNotes")}
            </span>
            {notesExpanded ? (
              <ChevronUp className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            )}
          </button>
          {notesExpanded && (
            <div className="p-3 text-sm text-muted-foreground whitespace-pre-wrap">
              {analysisNotes}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
