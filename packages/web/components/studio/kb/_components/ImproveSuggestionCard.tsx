"use client";

/**
 * Single suggestion card for the KB improve panel.
 *
 * Renders the suggestion with type icon, confidence bar,
 * proposed content, reasoning, and accept/reject actions.
 */

import { Check, X } from "lucide-react";
import { useTranslations } from "next-intl";

import type { ImproveSuggestion } from "@/lib/api/kb-improve";

import {
  DEFAULT_COLOR_CLASS,
  DEFAULT_ICON,
  getTypeLabel,
  TYPE_COLORS,
  TYPE_ICONS,
} from "./improve-constants";

interface ImproveSuggestionCardProps {
  suggestion: ImproveSuggestion;
  isSelected: boolean;
  onToggle: (id: number) => void;
  onAccept: (id: number) => void;
  onReject: (id: number) => void;
}

export function ImproveSuggestionCard({
  suggestion,
  isSelected,
  onToggle,
  onAccept,
  onReject,
}: ImproveSuggestionCardProps) {
  const t = useTranslations("studio");

  const IconComponent = TYPE_ICONS[suggestion.type] ?? DEFAULT_ICON;
  const colorClass = TYPE_COLORS[suggestion.type] ?? DEFAULT_COLOR_CLASS;

  return (
    <div
      className={`border rounded-lg overflow-hidden transition-colors ${
        isSelected ? "border-primary/50 bg-primary/5" : "border-border bg-card"
      }`}
    >
      {/* Suggestion header */}
      <button
        type="button"
        className="w-full flex items-center justify-between p-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
        onClick={() => onToggle(suggestion.suggestion_id)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div
            className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
              isSelected ? "bg-primary border-primary" : "border-muted-foreground/40"
            }`}
          >
            {isSelected && <Check className="w-3.5 h-3.5 text-primary-foreground" />}
          </div>
          <div
            className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 ${colorClass}`}
          >
            <IconComponent className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                {getTypeLabel(suggestion.type, t)}
              </span>
              <span className="text-xs text-purple-500 font-medium">
                {Math.round(suggestion.confidence * 100)}%
              </span>
            </div>
            <p className="text-sm font-medium truncate">{suggestion.description}</p>
          </div>
        </div>
        {isSelected && (
          <span className="text-xs text-green-600 dark:text-green-400 flex-shrink-0">
            {t("kb.willApply")}
          </span>
        )}
      </button>

      {/* Confidence bar */}
      <div className="px-4 py-1.5">
        <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-purple-400/60 rounded-full"
            style={{ width: `${Math.round(suggestion.confidence * 100)}%` }}
          />
        </div>
      </div>

      {/* Proposed content or related entity */}
      {(suggestion.proposed_content || suggestion.related_entity_name) && (
        <div className="px-4 pb-2">
          <div className="p-3 bg-muted/20 rounded-md text-sm text-muted-foreground">
            {suggestion.proposed_content ? (
              <span className="italic">
                {"\u201c"}
                {suggestion.proposed_content}
                {"\u201d"}
              </span>
            ) : null}
            {suggestion.related_entity_name ? (
              <span>
                {suggestion.proposed_content ? <br /> : null}
                <span className="text-xs font-medium text-purple-500">
                  {suggestion.related_entity_name}
                </span>
              </span>
            ) : null}
          </div>
        </div>
      )}

      {/* Reasoning */}
      {suggestion.reasoning && (
        <div className="px-4 pb-3">
          <div className="text-xs text-muted-foreground italic">{suggestion.reasoning}</div>
        </div>
      )}

      {/* Quick accept/reject buttons */}
      <div className="flex justify-end gap-2 p-3 border-t border-border/50 bg-muted/20">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onReject(suggestion.suggestion_id);
          }}
          className="flex items-center gap-1 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors"
        >
          <X className="w-3 h-3" />
          {t("aiActions.reject")}
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onAccept(suggestion.suggestion_id);
          }}
          className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
        >
          <Check className="w-3 h-3" />
          {t("aiActions.accept")}
        </button>
      </div>
    </div>
  );
}
