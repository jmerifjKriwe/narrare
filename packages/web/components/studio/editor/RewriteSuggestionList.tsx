"use client";

import { Check } from "lucide-react";
import { AIDiffView } from "@/components/shared/ai-diff/AIDiffView";
import { rewriteAdapter } from "@/lib/ai-diff/adapters/rewrite";
import type { AISuggestion } from "./TipTapEditorController";

interface RewriteSuggestionListProps {
  aiSuggestion: AISuggestion;
  selectedSuggestion: number;
  onSelectedSuggestionChange: (index: number) => void;
  isRewriteStreaming: boolean;
}

/**
 * Renders the rewrite alternatives as selectable cards.
 *
 * Each alternative is shown through the shared AIDiffView (CR-AUFG-07-18) so
 * the badge + accessible ins/del diff stays consistent across Rewrite /
 * Co-Author / KB Enhance. Extracted from RewriteSuggestionModal for RULE-04
 * modularity; purely presentational — no state of its own.
 */
export function RewriteSuggestionList({
  aiSuggestion,
  selectedSuggestion,
  onSelectedSuggestionChange,
  isRewriteStreaming,
}: RewriteSuggestionListProps) {
  return (
    <div className="space-y-3">
      {aiSuggestion.suggestions.map((suggestion, index) => (
        <button
          type="button"
          key={`suggestion-${suggestion.slice(0, 32)}`}
          onClick={() => onSelectedSuggestionChange(index)}
          className={`w-full text-left p-4 rounded-lg border-2 transition-all ${selectedSuggestion === index ? "border-primary bg-accent" : "border-border hover:border-primary/50"}`}
        >
          {aiSuggestion.labels[index] && (
            <p className="text-xs font-medium text-muted-foreground mb-2">
              {aiSuggestion.labels[index]}
            </p>
          )}
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              {/*
                CR-AUFG-07-18: shared AIDiffView (text mode). The label
                is passed via the adapter so the badge + label grouping is
                consistent across Rewrite/Co-Author/KB Enhance. The
                standalone label <p> above is kept for visual hierarchy;
                the adapter receives null here to avoid a duplicate label
                inside AIDiffView's header.
              */}
              <AIDiffView
                viewModel={rewriteAdapter(
                  aiSuggestion.original,
                  suggestion,
                  null,
                  isRewriteStreaming,
                )}
                state="suggested"
              />
            </div>
            {selectedSuggestion === index && (
              <Check className="w-5 h-5 text-primary flex-shrink-0" />
            )}
          </div>
        </button>
      ))}
    </div>
  );
}
