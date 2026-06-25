"use client";

/**
 * Style-variant regeneration section for the Co-Author review phase
 * (CR-AUFG-07-22 Increment B).
 *
 * Renders the "Regenerate as…" picker, the streaming/error states, and the
 * regenerated variant preview alongside the original Co-Author output. The
 * original output stays visible and unchanged (spec: "original remains visible
 * until a variant is accepted"); the variant result is surfaced below for
 * comparison.
 *
 * Extracted from CoAuthorReviewPhase per RULE-04 (component hard limit 200).
 * i18n reuses shared studio.styleVariants.* / studio.aiActions.* keys.
 */

import { AlertTriangle, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { StyleVariant } from "@/lib/api/generation";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";

import { StyleVariantPicker } from "../StyleVariantPicker";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CoAuthorStyleVariantSectionProps {
  /** Currently selected style variant, or null when nothing chosen yet. */
  readonly selectedVariant: StyleVariant | null;
  /** Fire when the writer picks a variant to regenerate the output as. */
  readonly onSelectVariant: (variant: StyleVariant) => void;
  /** Regenerated passage text (empty until the variant stream completes). */
  readonly variantText: string;
  /** True while a style-variant regeneration is streaming. */
  readonly isVariantStreaming: boolean;
  /** Structured error from the last variant stream (null when none). */
  readonly variantError: AIErrorResponse | null;
  /** Disable the picker while the parent apply is in flight. */
  readonly disabled?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CoAuthorStyleVariantSection({
  selectedVariant,
  onSelectVariant,
  variantText,
  isVariantStreaming,
  variantError,
  disabled = false,
}: CoAuthorStyleVariantSectionProps) {
  const t = useTranslations("studio");

  return (
    <div className="pt-3 mt-1 border-t border-border space-y-3">
      <StyleVariantPicker
        selectedVariant={selectedVariant}
        onSelect={onSelectVariant}
        isStreaming={isVariantStreaming || disabled}
        t={t}
      />

      {isVariantStreaming && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>{t("aiActions.generating")}</span>
        </div>
      )}

      {variantError && !isVariantStreaming && (
        <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-lg text-sm">
          <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
          <p className="text-red-700 dark:text-red-400 font-medium">
            {resolveErrorMessage(variantError, t)}
          </p>
        </div>
      )}

      {!isVariantStreaming && variantText && selectedVariant && (
        <div
          className="rounded-lg border border-primary/30 bg-primary/5 p-3"
          data-testid="coauthor-variant-result"
        >
          <p className="text-xs font-medium text-primary mb-1.5">
            {t(`styleVariants.${selectedVariant}.label`)}
          </p>
          <p className="text-sm whitespace-pre-wrap">{variantText}</p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type StudioTranslator = ReturnType<typeof useTranslations>;

/**
 * Resolve a structured AIErrorResponse to a user-facing message for the variant
 * surface. Uses the i18n key when available, falls back to the mapped
 * userMessage (mirrors RewriteSuggestionModal's error resolution).
 */
function resolveErrorMessage(error: AIErrorResponse, t: StudioTranslator): string {
  try {
    return t(error.i18nKey as Parameters<typeof t>[0]);
  } catch {
    return error.userMessage || t("aiActions.errorDefault");
  }
}
