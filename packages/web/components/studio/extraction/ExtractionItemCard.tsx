"use client";

/**
 * ExtractionItemCard — Single extraction result with type badge,
 * confidence bar, source text, and endorse/reject checkbox.
 *
 * Follows KBEnhanceReview endorse/reject pattern.
 */

import { AlertTriangle, Check, ChevronDown, ChevronUp } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { ExtractionItem, ExtractionItemType } from "@/lib/api/extraction";

// --- Badge color map by item type ---

const BADGE_STYLES: Record<ExtractionItemType, string> = {
  new_entity: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  update_entity: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  relationship: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  conflict: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
};

const CONFIDENCE_COLORS: Record<string, string> = {
  high: "bg-green-500",
  medium: "bg-yellow-500",
  low: "bg-red-500",
};

function confidenceLevel(score: number): string {
  if (score >= 0.8) return "high";
  if (score >= 0.5) return "medium";
  return "low";
}

interface ExtractionItemCardProps {
  item: ExtractionItem;
  isSelected: boolean;
  onToggle: () => void;
}

export function ExtractionItemCard({ item, isSelected, onToggle }: ExtractionItemCardProps) {
  const t = useTranslations("studio");
  const [sourceExpanded, setSourceExpanded] = useState(false);

  const badgeLabel: Record<ExtractionItemType, string> = {
    new_entity: t("kb.extractionNewEntity"),
    update_entity: t("kb.extractionUpdateEntity"),
    relationship: t("kb.extractionRelationship"),
    conflict: t("kb.extractionConflict"),
  };

  const pct = Math.round(item.confidence * 100);
  const level = confidenceLevel(item.confidence);

  return (
    <div
      className={`border rounded-lg overflow-hidden transition-colors ${
        isSelected ? "border-primary/50 bg-primary/5" : "border-border bg-card"
      }`}
    >
      {/* Header row: checkbox + type badge + name */}
      <button
        type="button"
        className="w-full flex items-center gap-3 p-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
        onClick={onToggle}
      >
        <div
          className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors flex-shrink-0 ${
            isSelected ? "bg-primary border-primary" : "border-muted-foreground/40"
          }`}
        >
          {isSelected && <Check className="w-3.5 h-3.5 text-primary-foreground" />}
        </div>
        <span className={`text-xs px-2 py-0.5 rounded font-medium ${BADGE_STYLES[item.item_type]}`}>
          {item.item_type === "conflict" && <AlertTriangle className="w-3 h-3 inline mr-1" />}
          {badgeLabel[item.item_type]}
        </span>
        <span className="text-sm font-medium truncate flex-1">
          {item.item_type === "relationship"
            ? t("kb.extractionRelationshipFormat", {
                name: item.name,
                related: item.related_entity_name ?? "",
              })
            : item.name}
        </span>
        {item.entity_type && (
          <span className="text-xs text-muted-foreground">{item.entity_type}</span>
        )}
      </button>

      {/* Confidence bar */}
      <div className="px-3 py-2">
        <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
          <span>{t("kb.extractionConfidenceLabel", { score: pct })}</span>
        </div>
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${CONFIDENCE_COLORS[level]}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Conflict description */}
      {item.item_type === "conflict" && item.conflict_description && (
        <div className="px-3 pb-2">
          <p className="text-xs text-amber-600 dark:text-amber-400">
            {t("kb.extractionConflictDescription", { description: item.conflict_description })}
          </p>
        </div>
      )}

      {/* Proposed content (for new/update entities) */}
      {item.proposed_content && (
        <div className="px-3 pb-2">
          <div className="text-xs font-medium text-muted-foreground mb-1">
            {t("kb.extractionProposedContent")}
          </div>
          <pre className="text-xs bg-muted/50 rounded p-2 overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(item.proposed_content, null, 2)}
          </pre>
        </div>
      )}

      {/* Source text (collapsible) */}
      {item.source_text && (
        <div className="px-3 pb-2">
          <button
            type="button"
            onClick={() => setSourceExpanded((prev) => !prev)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {sourceExpanded ? (
              <ChevronUp className="w-3 h-3" />
            ) : (
              <ChevronDown className="w-3 h-3" />
            )}
            {sourceExpanded ? t("kb.extractionHideSource") : t("kb.extractionViewSource")}
          </button>
          {sourceExpanded && (
            <p className="mt-1 text-xs text-muted-foreground italic">
              {t("kb.extractionSourceText", { text: item.source_text })}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
