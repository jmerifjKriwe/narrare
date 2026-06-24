"use client";

/**
 * PromptHistoryList — presentational revision list (CR-AUFG-07-19).
 *
 * Stateless: receives revisions + a restore handler. The active revision is
 * rendered read-only (no restore button) because restoring the active content
 * is a no-op. Dates are formatted via ``Intl.DateTimeFormat`` (locale-aware).
 */
import { useTranslations } from "next-intl";
import type { PromptRevision } from "@/types";

interface PromptHistoryListProps {
  readonly revisions: readonly PromptRevision[];
  readonly onRestore: (revision: PromptRevision) => void;
  readonly isRestorePending: boolean;
  /** Revision id currently being restored (disables + shows "restoring"). */
  readonly restoringId: string | null;
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function PromptHistoryList({
  revisions,
  onRestore,
  isRestorePending,
  restoringId,
}: PromptHistoryListProps) {
  const t = useTranslations("studio");

  return (
    <ul className="divide-y divide-border rounded-md border border-border">
      {revisions.map((rev) => {
        const isActive = rev.is_active;
        const isThisRestoring = isRestorePending && restoringId === rev.id;
        return (
          <li key={rev.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
            <div className="min-w-0 space-y-0.5">
              <div className="flex items-center gap-2">
                {isActive && (
                  <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-medium text-primary">
                    {t("settings.prompts.promptHistory.activeBadge")}
                  </span>
                )}
                <span className="font-mono text-xs text-muted-foreground">
                  {rev.id.slice(0, 8)}
                </span>
              </div>
              <div className="text-xs text-muted-foreground">
                <span>{t("settings.prompts.promptHistory.dateLabel")}: </span>
                <time dateTime={rev.created_at}>{formatDate(rev.created_at)}</time>
                <span className="mx-1.5">·</span>
                <span>{t("settings.prompts.promptHistory.sourceLabel")}: </span>
                <span>{rev.source}</span>
              </div>
            </div>
            {/* The active revision cannot be restored (it IS the current
                content) — no action button. Its state is conveyed by the
                "Active" badge above. Non-active rows get a restore button. */}
            {isActive ? null : (
              <button
                type="button"
                disabled={isRestorePending}
                onClick={() => onRestore(rev)}
                aria-label={
                  isThisRestoring
                    ? t("settings.prompts.promptHistory.restoring")
                    : t("settings.prompts.promptHistory.restore")
                }
                className="shrink-0 rounded-md bg-muted px-3 py-1.5 text-xs hover:bg-accent transition-colors disabled:opacity-50"
              >
                {isThisRestoring
                  ? t("settings.prompts.promptHistory.restoring")
                  : t("settings.prompts.promptHistory.restore")}
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
