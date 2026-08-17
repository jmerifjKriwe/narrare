"use client";

/**
 * SeriesDriftResultSection — shared result-section shell for the Cross-Novel
 * Drift panel (Spec 4 Task 4; extracted from `SeriesDriftPanel` per RULE-04
 * in the C2 drift-persistence fix round).
 *
 * Renders one check's titled section with its loading / error / content
 * state: while pending a spinner plus loading copy, on error the error copy,
 * otherwise the caller's children (the actual result renderer, e.g.
 * `SeriesConflictList` or `SeriesDriftSummary`).
 *
 * The section div's data-testid is caller-supplied; the loading / error
 * paragraphs derive theirs as ``${testId}-loading`` / ``${testId}-error``.
 *
 * All copy via ``useTranslations("studio")``; the message keys are passed in
 * by the caller (`loadingKey` / `errorKey`).
 */
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";

interface SeriesDriftResultSectionProps {
  /** data-testid of the section div; loading/error testids derive from it. */
  readonly testId: string;
  /** Section heading text (already translated by the caller). */
  readonly title: string;
  /** Whether the check is currently running (shows the loading state). */
  readonly isPending: boolean;
  /** Whether the check failed (shows the error state). */
  readonly isError: boolean;
  /** Studio message key for the loading copy. */
  readonly loadingKey: string;
  /** Studio message key for the error copy. */
  readonly errorKey: string;
  /** Result renderer, shown when neither pending nor error. */
  readonly children: React.ReactNode;
}

export function SeriesDriftResultSection({
  testId,
  title,
  isPending,
  isError,
  loadingKey,
  errorKey,
  children,
}: SeriesDriftResultSectionProps) {
  const t = useTranslations("studio");
  return (
    <div data-testid={testId} className="space-y-2">
      <h3 className="text-sm font-medium text-foreground">{title}</h3>
      {isPending ? (
        <p
          data-testid={`${testId}-loading`}
          className="flex items-center gap-2 py-2 text-sm text-muted-foreground"
        >
          <Loader2 className="h-4 w-4 animate-spin" />
          {t(loadingKey)}
        </p>
      ) : isError ? (
        <p data-testid={`${testId}-error`} className="py-2 text-sm text-destructive">
          {t(errorKey)}
        </p>
      ) : (
        children
      )}
    </div>
  );
}
