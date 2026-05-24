"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";

import { aiSettingsApi, type ModelRefreshResponse } from "@/lib/api/client";

/**
 * ModelDataStatus component.
 *
 * Displays the current state of the local model data cache and allows
 * the user to trigger a manual refresh from the community-maintained
 * models.dev database via POST /api/v1/settings/models/refresh.
 *
 * States handled:
 * - Idle: shows the refresh button only.
 * - Loading: spinner on the button + a "Refreshing..." status line.
 * - Success with new models: green checkmark + count.
 * - Success with removed models: amber alert + count.
 * - Success with no changes: "up to date" message.
 * - Error from API: red alert with message.
 * - Network/mutation error: generic error fallback.
 */
export function ModelDataStatus() {
  const t = useTranslations("studio");

  const refreshMutation = useMutation<ModelRefreshResponse, Error>({
    mutationFn: () => aiSettingsApi.refreshModels(),
  });

  const { data, isPending, error } = refreshMutation;

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
          <span className="text-lg" aria-hidden="true">
            📡
          </span>
        </div>
        <div>
          <h3 className="font-medium">{t("settings.ai.modelData.title")}</h3>
          <p className="text-sm text-muted-foreground">{t("settings.ai.modelData.description")}</p>
        </div>
      </div>

      {/* Refresh button */}
      <button
        type="button"
        onClick={() => refreshMutation.mutate()}
        disabled={isPending}
        aria-busy={isPending}
        className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isPending ? (
          <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
        ) : (
          <RefreshCw className="w-4 h-4" aria-hidden="true" />
        )}
        {t("settings.ai.modelData.refreshButton")}
      </button>

      {/* Loading indicator */}
      {isPending && (
        <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
          <span aria-live="polite">{t("settings.ai.modelData.refreshing")}</span>
        </div>
      )}

      {/* Success state */}
      {data?.status === "ok" && (
        <div className="mt-3 space-y-1" aria-live="polite">
          {data.new_models.length > 0 && (
            <p className="text-sm text-green-600 dark:text-green-400 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>
                {t("settings.ai.modelData.newModels", {
                  count: data.new_models.length,
                })}
              </span>
            </p>
          )}
          {data.removed_models.length > 0 && (
            <p className="text-sm text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
              <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>
                {t("settings.ai.modelData.deprecatedModels", {
                  count: data.removed_models.length,
                })}
              </span>
            </p>
          )}
          {data.new_models.length === 0 && data.removed_models.length === 0 && (
            <p className="text-sm text-muted-foreground flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>{t("settings.ai.modelData.upToDate")}</span>
            </p>
          )}
          <p className="text-xs text-muted-foreground mt-1">
            {new Date(data.cached_at).toLocaleString()}
          </p>
        </div>
      )}

      {/* API error state */}
      {data?.status === "error" && (
        <div className="mt-3 flex items-center gap-1.5 text-sm text-red-600 dark:text-red-400">
          <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span aria-live="assertive">{data.message || t("settings.ai.modelData.error")}</span>
        </div>
      )}

      {/* Network / mutation error state */}
      {error && (
        <div className="mt-3 flex items-center gap-1.5 text-sm text-red-600 dark:text-red-400">
          <AlertCircle className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span aria-live="assertive">{t("settings.ai.modelData.error")}</span>
        </div>
      )}
    </div>
  );
}
