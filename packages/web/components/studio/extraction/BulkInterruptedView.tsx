"use client";

/**
 * BulkInterruptedView — INTERRUPTED degrade of `BulkExtractionPanel` (F2 T7):
 * explains that the job was lost (most likely a server restart) and that
 * nothing was written to the KB, and offers a clean restart via reset+start.
 *
 * @module BulkInterruptedView
 */

import { useTranslations } from "next-intl";

interface BulkInterruptedViewProps {
  readonly title: string;
  readonly onRestart: () => void;
}

export function BulkInterruptedView({ title, onRestart }: BulkInterruptedViewProps) {
  const t = useTranslations("studio");

  return (
    <section aria-label={title} className="space-y-4 text-center py-8">
      <p className="text-sm text-muted-foreground max-w-md mx-auto">
        {t("kb.bulkExtraction.interruptedBody")}
      </p>
      <button
        type="button"
        onClick={onRestart}
        className="px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        {t("kb.bulkExtraction.restart")}
      </button>
    </section>
  );
}
