"use client";

import { Download, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ExportJobStatus } from "@/types";

/**
 * ExportFooterActions — the panel footer's state-aware action area.
 *
 * Extracted from ExportPanel for RULE-04 file-size compliance. Renders
 * exactly one of: Download + start-new (completed), start-new (failed),
 * or the Export button (idle / in-flight).
 */

interface ExportFooterActionsProps {
  /** Status of the active job; `undefined` when idle. */
  readonly jobStatus: ExportJobStatus | undefined;
  readonly isExporting: boolean;
  /** True while a create mutation or download is in flight (spinner). */
  readonly isBusy: boolean;
  readonly exportDisabled: boolean;
  readonly downloadPending: boolean;
  readonly downloadFailed: boolean;
  readonly onExport: () => void;
  readonly onDownload: () => void;
  readonly onStartNew: () => void;
}

export function ExportFooterActions({
  jobStatus,
  isExporting,
  isBusy,
  exportDisabled,
  downloadPending,
  downloadFailed,
  onExport,
  onDownload,
  onStartNew,
}: ExportFooterActionsProps) {
  const t = useTranslations("export");

  if (jobStatus === "completed") {
    return (
      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={onDownload}
          disabled={downloadPending}
          className="flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90 transition-opacity disabled:opacity-50"
          data-testid="export-download"
        >
          {downloadPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          {t("status.download")}
        </button>
        {downloadFailed && (
          <p role="alert" className="text-center text-xs text-destructive">
            {t("errors.downloadFailed")}
          </p>
        )}
        <button
          type="button"
          onClick={onStartNew}
          className="text-center text-xs text-muted-foreground hover:text-foreground"
        >
          {t("status.startNew")}
        </button>
      </div>
    );
  }

  if (jobStatus === "failed") {
    return (
      <button
        type="button"
        onClick={onStartNew}
        className="w-full rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground hover:bg-accent transition-colors"
      >
        {t("status.startNew")}
      </button>
    );
  }

  // Idle or in-flight: the Export button.
  return (
    <button
      type="button"
      onClick={onExport}
      disabled={exportDisabled}
      className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90 transition-opacity disabled:opacity-50"
      data-testid="export-submit"
    >
      {isBusy && <Loader2 className="h-4 w-4 animate-spin" />}
      {isExporting ? t("export.exporting") : t("export.action")}
    </button>
  );
}
