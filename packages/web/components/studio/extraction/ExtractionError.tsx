"use client";

/**
 * ExtractionError — Error state with retry button.
 *
 * Rendered via the shared `StatusMessage` primitive, which provides the
 * accessible `role="alert"` / assertive live region and standardised
 * destructive styling. The caller resolves the i18n message and retry label.
 */

import { useTranslations } from "next-intl";
import { StatusMessage } from "@/components/ui/status-message";

interface ExtractionErrorProps {
  readonly message: string;
  readonly onRetry: () => void;
}

export function ExtractionError({ message, onRetry }: ExtractionErrorProps) {
  const t = useTranslations("studio");

  return (
    <StatusMessage
      state="error"
      message={message}
      action={
        <button type="button" onClick={onRetry} aria-label={t("kb.extractionRetry")}>
          {t("kb.extractionRetry")}
        </button>
      }
    />
  );
}
