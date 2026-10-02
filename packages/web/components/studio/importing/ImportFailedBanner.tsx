"use client";

import { useTranslations } from "next-intl";

/**
 * ImportFailedBanner — presentational retry banner after a failed import commit.
 *
 * Copy is single-sourced from the importing namespace (Task 7) — the wizard and
 * this banner must never drift. Extracted from SidebarChapterList.tsx (RULE-04);
 * state ownership (sessionStorage flag, modal open state) stays in the parent.
 */

export function ImportFailedBanner({
  onRetry,
  onDismiss,
}: {
  /** Reopen the import wizard so the user can retry the failed commit. */
  onRetry: () => void;
  /** Clear the sessionStorage flag and hide the banner. */
  onDismiss: () => void;
}) {
  const tImport = useTranslations("importing.failedBanner");

  return (
    <div
      role="alert"
      data-testid="import-failed-banner"
      className="mt-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-xs"
    >
      <p className="font-medium text-destructive">{tImport("title")}</p>
      <p className="mt-1 text-muted-foreground">{tImport("body")}</p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          data-testid="import-retry-btn"
          onClick={onRetry}
          className="rounded bg-primary px-2 py-1 font-medium text-primary-foreground hover:opacity-90 transition-opacity"
        >
          {tImport("retry")}
        </button>
        <button
          type="button"
          data-testid="import-dismiss-btn"
          onClick={onDismiss}
          className="rounded px-2 py-1 text-muted-foreground hover:text-foreground transition-colors"
        >
          {tImport("dismiss")}
        </button>
      </div>
    </div>
  );
}
