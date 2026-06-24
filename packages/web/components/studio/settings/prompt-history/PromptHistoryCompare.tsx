"use client";

/**
 * PromptHistoryCompare — from/to revision selector + shared diff view.
 *
 * Presentational (CR-AUFG-07-19): receives the current from/to selection and
 * the resolved compare payload, then renders the shared
 * :component:`AIDiffView` via :func:`promptHistoryDiffAdapter`. Owns NO data —
 * selection state and the compare query live in :func:`usePromptHistory`
 * (RULE-04 split). RULE-07: the component depends on the shared diff lib, never
 * the reverse.
 *
 * The "Active override" pseudo-revision uses ``PROMPT_HISTORY_ACTIVE_TOKEN`` so
 * the backend compare endpoint resolves it to the current active content
 * (``history_mapping.ACTIVE_TOKEN``).
 *
 * History is never streaming, so the diff ``state`` is derived deterministically
 * from whether the two contents differ (``unchanged`` vs ``suggested``).
 */
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { AIDiffView } from "@/components/shared/ai-diff/AIDiffView";
import type { AIDiffState } from "@/lib/ai-diff";
import { promptHistoryDiffAdapter } from "@/lib/ai-diff";
import type { PromptRevision, PromptRevisionCompareResponse } from "@/types";
import { PROMPT_HISTORY_ACTIVE_TOKEN } from "@/types";

interface PromptHistoryCompareProps {
  readonly revisions: readonly PromptRevision[];
  readonly fromId: string | null;
  readonly toId: string | null;
  readonly onFromChange: (id: string) => void;
  readonly onToChange: (id: string) => void;
  readonly compare: PromptRevisionCompareResponse | undefined;
  readonly isLoading: boolean;
  readonly isError: boolean;
}

/** Short, stable, human-readable label for a revision option. */
function revisionLabel(rev: PromptRevision): string {
  return `${rev.source} · ${rev.id.slice(0, 8)}`;
}

export function PromptHistoryCompare({
  revisions,
  fromId,
  toId,
  onFromChange,
  onToChange,
  compare,
  isLoading,
  isError,
}: PromptHistoryCompareProps) {
  const t = useTranslations("studio");
  const bothSelected = fromId !== null && toId !== null;

  // Shared option list (placeholder + active pseudo-revision + each revision).
  const options: ReactNode = (
    <>
      <option value="" disabled>
        {t("settings.prompts.promptHistory.selectPlaceholder")}
      </option>
      <option value={PROMPT_HISTORY_ACTIVE_TOKEN}>
        {t("settings.prompts.promptHistory.activeOption")}
      </option>
      {revisions.map((rev) => (
        <option key={rev.id} value={rev.id}>
          {revisionLabel(rev)}
        </option>
      ))}
    </>
  );

  const state: AIDiffState =
    compare && compare.from_content === compare.to_content ? "unchanged" : "suggested";

  return (
    <div className="space-y-3">
      <div>
        <h4 className="text-sm font-medium text-foreground">
          {t("settings.prompts.promptHistory.compareTitle")}
        </h4>
        <p className="text-xs text-muted-foreground">
          {t("settings.prompts.promptHistory.compareHint")}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {t("settings.prompts.promptHistory.fromLabel")}
          </span>
          <select
            value={fromId ?? ""}
            onChange={(e) => onFromChange(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            aria-label={t("settings.prompts.promptHistory.fromLabel")}
          >
            {options}
          </select>
        </label>

        <label className="space-y-1 text-sm">
          <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {t("settings.prompts.promptHistory.toLabel")}
          </span>
          <select
            value={toId ?? ""}
            onChange={(e) => onToChange(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            aria-label={t("settings.prompts.promptHistory.toLabel")}
          >
            {options}
          </select>
        </label>
      </div>

      {bothSelected && isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("settings.prompts.promptHistory.compareLoading")}
        </div>
      )}

      {bothSelected && isError && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">
          {t("settings.prompts.promptHistory.compareFailed")}
        </div>
      )}

      {bothSelected && !isLoading && !isError && compare && (
        <AIDiffView viewModel={promptHistoryDiffAdapter(compare)} state={state} />
      )}
    </div>
  );
}
