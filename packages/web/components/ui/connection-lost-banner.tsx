"use client";

import { WifiOff } from "lucide-react";
import { useTranslations } from "next-intl";

interface ConnectionLostBannerProps {
  /** Callback when the user clicks the retry button. */
  readonly onRetry: () => void;
  /** Override the default "connection lost" message. */
  readonly message?: string;
}

/**
 * Reusable banner shown when an SSE stream or AI connection drops.
 *
 * Uses design tokens for theming (amber/yellow accent) and i18n keys from
 * the `studio.aiActions` namespace.
 */
export function ConnectionLostBanner({ onRetry, message }: ConnectionLostBannerProps) {
  const t = useTranslations("studio.aiActions");

  return (
    <div
      className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/30"
      role="alert"
    >
      <WifiOff className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
      <span className="flex-1 text-sm text-amber-800 dark:text-amber-200">
        {message ?? t("connectionLost")}
      </span>
      <button
        type="button"
        onClick={onRetry}
        className="text-sm font-medium text-amber-700 hover:underline dark:text-amber-300"
      >
        {t("connectionLostRetry")}
      </button>
    </div>
  );
}
