"use client";

/**
 * UnblockSuggestionCard — a single story-direction suggestion (WRITE-009).
 *
 * Renders the suggestion-type badge, title, description, and connection text
 * for one {@link StorySuggestion}, plus an "Accept" action. Extracted from
 * {@link UnblockPanel} for single responsibility and to keep the panel under
 * the file-size limit (RULE-04 / RULE-06).
 *
 * The type badge resolves the i18n key `studio.unblock.suggestionType.{type}`;
 * unknown types fall back to the raw value (the SSE contract tolerates unknown
 * values, see {@link StorySuggestionType}).
 *
 * @module UnblockSuggestionCard
 */

import { Check } from "lucide-react";
import type { useTranslations } from "next-intl";
import { AI_APPLY_ARIA_SHORTCUT } from "@/lib/ai-action-shortcuts";
import type { StorySuggestion } from "@/lib/api/story-suggest-stream";

type StudioTranslator = ReturnType<typeof useTranslations>;

interface UnblockSuggestionCardProps {
  /** The suggestion to render. */
  readonly suggestion: StorySuggestion;
  /** Position in the list — used for accessible aria-labelledby wiring. */
  readonly index: number;
  /** Called when the user accepts this suggestion. */
  readonly onAccept: (suggestion: StorySuggestion) => void;
  /** Studio-scoped translator (useTranslations("studio")). */
  readonly t: StudioTranslator;
}

/**
 * Render the human-readable label for a suggestion type.
 *
 * Resolves `unblock.suggestionType.{type}` via i18n. Falls back to the raw
 * type string when the key is missing so unknown backend values are tolerated
 * (see the StorySuggestionType contract in story-suggest-stream.ts).
 */
function renderTypeLabel(type: string, t: StudioTranslator): string {
  try {
    return t(`unblock.suggestionType.${type}` as Parameters<typeof t>[0]);
  } catch {
    return type;
  }
}

export function UnblockSuggestionCard({
  suggestion,
  index,
  onAccept,
  t,
}: UnblockSuggestionCardProps) {
  const titleId = `unblock-suggestion-${index}-title`;
  const typeLabel = renderTypeLabel(suggestion.type, t);

  return (
    <article
      className="flex flex-col gap-2 border border-border rounded-lg bg-card p-4"
      aria-labelledby={titleId}
    >
      <span className="inline-flex w-fit items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
        {typeLabel}
      </span>

      <h4 id={titleId} className="text-sm font-medium">
        {suggestion.title}
      </h4>

      {suggestion.description ? (
        <p className="text-sm text-muted-foreground">{suggestion.description}</p>
      ) : null}

      {suggestion.connection ? (
        <p className="text-xs italic text-muted-foreground">{suggestion.connection}</p>
      ) : null}

      <div className="mt-1">
        <button
          type="button"
          onClick={() => onAccept(suggestion)}
          aria-keyshortcuts={AI_APPLY_ARIA_SHORTCUT}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Check className="h-3.5 w-3.5" />
          {t("aiActions.accept")}
        </button>
      </div>
    </article>
  );
}
