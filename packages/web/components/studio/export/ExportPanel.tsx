"use client";

import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { overlayVariants, panelSlideRightVariants } from "@/lib/motion-variants";
import { ExportFooterActions } from "./ExportFooterActions";
import { ExportJobStatusView } from "./ExportJobStatusView";
import { ExportOptionsForm } from "./ExportOptionsForm";
import { useExportPanel } from "./useExportPanel";

interface ExportPanelProps {
  readonly novelId: string;
  readonly isOpen: boolean;
  readonly onClose: () => void;
}

export function ExportPanel({ novelId, isOpen, onClose }: ExportPanelProps) {
  const t = useTranslations("export");
  const panel = useExportPanel(novelId);

  const job = panel.job;
  const hasActiveJob = !!job;
  const isBusy = panel.isExporting || panel.downloadPending;
  const exportDisabled = panel.isExporting || !panel.isFormatAvailable(panel.options.format);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex"
          variants={overlayVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
        >
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
          />

          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={t("title")}
            variants={panelSlideRightVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="relative ml-auto flex w-full max-w-lg h-full flex-col overflow-hidden border-l border-border bg-card shadow-2xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-5 py-4 shrink-0">
              <div>
                <h2 className="text-base font-semibold text-foreground">{t("title")}</h2>
                <p className="text-xs text-muted-foreground">{t("subtitle")}</p>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label={t("close")}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-5 py-4">
              {panel.formatsFailed && (
                <p
                  role="alert"
                  className="mb-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive"
                >
                  {t("errors.formatsFailed")}
                </p>
              )}

              {hasActiveJob ? (
                <ExportJobStatusView status={job.status} error={job.error} />
              ) : (
                <>
                  {panel.createFailed && (
                    <p
                      role="alert"
                      data-testid="export-create-error"
                      className="mb-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive"
                    >
                      {t("errors.createFailed")}
                    </p>
                  )}
                  <ExportOptionsForm
                    options={panel.options}
                    isFormatAvailable={panel.isFormatAvailable}
                    disabled={panel.isExporting}
                    onChange={panel.setOptions}
                  />
                </>
              )}
            </div>

            {/* Footer actions */}
            <div className="border-t border-border px-5 py-4 shrink-0">
              <ExportFooterActions
                jobStatus={job?.status}
                isExporting={panel.isExporting}
                isBusy={isBusy}
                exportDisabled={exportDisabled}
                downloadPending={panel.downloadPending}
                downloadFailed={panel.downloadFailed}
                onExport={panel.handleExport}
                onDownload={panel.handleDownload}
                onStartNew={panel.startNewExport}
              />
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
