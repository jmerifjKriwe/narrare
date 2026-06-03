"use client";

/**
 * Review section for the KB improve panel.
 *
 * Renders completeness score, bulk selection actions,
 * empty state, and the list of suggestion cards.
 */

import { Check } from "lucide-react";
import { useTranslations } from "next-intl";

import type { ImproveSuggestion } from "@/lib/api/kb-improve";

import { ImproveSuggestionCard } from "./ImproveSuggestionCard";

interface ImproveReviewSectionProps {
  completenessScore: number;
  assessment: string;
  suggestions: ImproveSuggestion[];
  selectedIds: Set<number>;
  onSelectAll: () => void;
  onSelectNone: () => void;
  onToggleSuggestion: (id: number) => void;
  onAcceptSuggestion: (id: number) => void;
  onRejectSuggestion: (id: number) => void;
}

export function ImproveReviewSection({
  completenessScore,
  assessment,
  suggestions,
  selectedIds,
  onSelectAll,
  onSelectNone,
  onToggleSuggestion,
  onAcceptSuggestion,
  onRejectSuggestion,
}: ImproveReviewSectionProps) {
  const t = useTranslations("studio");

  return (
    <div className="space-y-4">
      {/* Completeness score + assessment */}
      <div className="flex items-start gap-4 p-4 bg-muted/30 rounded-lg">
        <div className="flex-shrink-0 flex flex-col items-center">
          <div className="text-2xl font-bold text-purple-500">
            {Math.round(completenessScore * 100)}%
          </div>
          <div className="text-xs text-muted-foreground">
            {t("kb.improve.completeness") || "Complete"}
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <div className="w-full h-2 bg-muted rounded-full overflow-hidden mb-2">
            <div
              className="h-full bg-purple-500 rounded-full transition-all duration-500"
              style={{ width: `${Math.round(completenessScore * 100)}%` }}
            />
          </div>
          <p className="text-sm text-muted-foreground">{assessment}</p>
        </div>
      </div>

      {/* Bulk actions */}
      {suggestions.length > 0 && (
        <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg">
          <span className="text-sm text-muted-foreground">
            {t("kb.enhancementsFound", { count: suggestions.length }) ||
              `${suggestions.length} suggestion(s) found`}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onSelectAll}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              {t("kb.selectAll") || "Select all"}
            </button>
            <span className="text-muted-foreground">|</span>
            <button
              type="button"
              onClick={onSelectNone}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              {t("kb.selectNone") || "Select none"}
            </button>
          </div>
        </div>
      )}

      {/* No suggestions state */}
      {suggestions.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-4">
            <Check className="w-6 h-6 text-green-500" />
          </div>
          <p className="text-lg font-medium mb-1">
            {t("kb.improve.noSuggestions") || "No improvement suggestions found."}
          </p>
          <p className="text-sm text-muted-foreground">
            {t("kb.improve.entryLooksGood") || "The entry looks comprehensive."}
          </p>
        </div>
      )}

      {/* Suggestion cards */}
      {suggestions.map((suggestion) => (
        <ImproveSuggestionCard
          key={suggestion.suggestion_id}
          suggestion={suggestion}
          isSelected={selectedIds.has(suggestion.suggestion_id)}
          onToggle={onToggleSuggestion}
          onAccept={onAcceptSuggestion}
          onReject={onRejectSuggestion}
        />
      ))}
    </div>
  );
}
