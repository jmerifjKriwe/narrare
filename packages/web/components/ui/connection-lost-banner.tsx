"use client";

import { useTranslations } from "next-intl";
import { StatusMessage } from "@/components/ui/status-message";

interface ConnectionLostBannerProps {
  /** Callback when the user clicks the retry button. */
  readonly onRetry: () => void;
  /** Override the default "connection lost" message. */
  readonly message?: string;
}

/**
 * Reusable banner shown when an SSE stream or AI connection drops.
 *
 * Thin wrapper over the shared `StatusMessage` primitive: the error is
 * announced via `role="alert"` / assertive live region, with the retry
 * control as the actionable `action`. i18n strings are resolved here and
 * passed down (RULE-16). The standardised destructive token styling
 * replaces the previous bespoke amber palette.
 */
export function ConnectionLostBanner({ onRetry, message }: ConnectionLostBannerProps) {
  const t = useTranslations("studio.aiActions");

  return (
    <StatusMessage
      state="error"
      message={message ?? t("connectionLost")}
      action={
        <button type="button" data-testid="connection-lost-banner-retry" onClick={onRetry}>
          {t("connectionLostRetry")}
        </button>
      }
    />
  );
}
