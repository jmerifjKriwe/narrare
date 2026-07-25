"use client";

/**
 * UnblockResults — suggestion results + actions (WRITE-009).
 *
 * Rendered once suggestions have finished streaming (the "complete" phase).
 * Shows an empty-state message when the stream returned no suggestions,
 * otherwise the list of {@link UnblockSuggestionCard}s plus a footer with
 * Dismiss / Regenerate actions. Extracted from {@link UnblockPanel} for single
 * responsibility and to keep the panel under the file-size limit
 * (RULE-04 / RULE-06).
 *
 * @module UnblockResults
 */

import { RefreshCw } from "lucide-react";
import { motion } from "motion/react";
import type { useTranslations } from "next-intl";
import type { StorySuggestion } from "@/lib/api/story-suggest-stream";
import { listContainerVariants, listItemVariants } from "@/lib/motion-variants";
import { UnblockSuggestionCard } from "./UnblockSuggestionCard";

type StudioTranslator = ReturnType<typeof useTranslations>;

interface UnblockResultsProps {
  /** Suggestions returned by the stream (non-undefined when complete). */
  readonly suggestions: StorySuggestion[];
  /** Called when the user accepts a suggestion. */
  readonly onAccept: (suggestion: StorySuggestion) => void;
  /** Called when the user dismisses the results (returns to the form). */
  readonly onDismiss: () => void;
  /** Called when the user requests fresh suggestions. */
  readonly onRegenerate: () => void;
  /** Studio-scoped translator (useTranslations("studio")). */
  readonly t: StudioTranslator;
}

export function UnblockResults({
  suggestions,
  onAccept,
  onDismiss,
  onRegenerate,
  t,
}: UnblockResultsProps) {
  if (suggestions.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("unblock.empty")}</p>;
  }

  return (
    <div className="space-y-4">
      <motion.ul
        variants={listContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-3"
      >
        {suggestions.map((suggestion, index) => (
          <motion.li key={`${suggestion.type}-${suggestion.title}`} variants={listItemVariants}>
            <UnblockSuggestionCard
              suggestion={suggestion}
              index={index}
              onAccept={onAccept}
              t={t}
            />
          </motion.li>
        ))}
      </motion.ul>

      <div className="flex items-center gap-2 border-t border-border pt-3">
        <button
          type="button"
          onClick={onDismiss}
          className="rounded-md border border-border px-3 py-1.5 text-sm transition-colors hover:bg-muted"
        >
          {t("aiActions.reject")}
        </button>
        <button
          type="button"
          onClick={onRegenerate}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm transition-colors hover:bg-muted"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          {t("aiActions.newSuggestions")}
        </button>
      </div>
    </div>
  );
}
