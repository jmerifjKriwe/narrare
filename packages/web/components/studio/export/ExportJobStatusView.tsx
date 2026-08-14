"use client";

import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ExportJobStatus } from "@/types";

/**
 * ExportJobStatusView — the centered job-progress view (pending / running /
 * completed / failed) shown while an export job is active.
 *
 * Extracted from ExportPanel for RULE-04 file-size compliance.
 */

/** Map a job status to its i18n message key. */
function statusMessageKey(status: ExportJobStatus): string {
  switch (status) {
    case "pending":
      return "status.pending";
    case "running":
      return "status.running";
    case "completed":
      return "status.completed";
    case "failed":
      return "status.failed";
  }
}

interface ExportJobStatusViewProps {
  readonly status: ExportJobStatus;
  readonly error: string | null;
}

export function ExportJobStatusView({ status, error }: ExportJobStatusViewProps) {
  const t = useTranslations("export");
  const failed = status === "failed";
  const completed = status === "completed";
  const Icon = failed ? AlertCircle : completed ? CheckCircle2 : Loader2;
  const spin = !failed && !completed;
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 py-10 text-center"
      data-testid="export-job-status"
    >
      <Icon
        className={
          spin
            ? "h-8 w-8 animate-spin text-primary"
            : failed
              ? "h-8 w-8 text-destructive"
              : "h-8 w-8 text-primary"
        }
        aria-hidden="true"
      />
      <p className="text-sm font-medium text-foreground">{t(statusMessageKey(status))}</p>
      {failed && error && (
        <p className="max-w-sm text-xs text-muted-foreground">
          {t("status.errorPrefix", { message: error })}
        </p>
      )}
    </div>
  );
}
