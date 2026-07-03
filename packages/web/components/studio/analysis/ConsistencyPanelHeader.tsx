import { ArrowLeft, Info, Loader2, RefreshCw, Shield, X } from "lucide-react";
import type { useTranslations } from "next-intl";
import { IconButton } from "@/components/ui/icon-button";

type ViewState = "idle" | "loading" | "results" | "error";
type StudioTranslator = ReturnType<typeof useTranslations>;

interface ConsistencyPanelHeaderProps {
  viewState: ViewState;
  isPending: boolean;
  onClose: () => void;
  onRefresh: () => void;
  /** Optional cancel handler — shown as stop button during loading/streaming. */
  onCancel?: () => void;
  t: (key: string) => string;
  tStudio: StudioTranslator;
}

export function ConsistencyPanelHeader({
  viewState,
  isPending,
  onClose,
  onRefresh,
  onCancel,
  t,
  tStudio,
}: ConsistencyPanelHeaderProps) {
  const isLoading = viewState === "loading";

  return (
    <>
      <div className="flex items-center justify-between p-4 border-b border-border bg-card">
        <div className="flex items-center gap-3 min-w-0">
          <IconButton label={t("close")} icon={ArrowLeft} onClick={onClose} />
          <div className="flex items-center gap-2 min-w-0">
            <Shield className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0" />
            <h3 className="font-medium truncate">{t("consistency.title")}</h3>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Stop button during loading */}
          {isLoading && onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-red-300 dark:border-red-800 text-red-600 dark:text-red-400 rounded-md hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
              aria-label={tStudio("aiActions.stop")}
            >
              <Loader2 className="w-3.5 h-3.5" />
              {tStudio("aiActions.stop")}
            </button>
          )}
          {viewState === "results" && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border rounded-md hover:bg-muted transition-colors disabled:opacity-50"
              aria-label={t("refresh")}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isPending ? "animate-spin" : ""}`} />
              {t("refresh")}
            </button>
          )}
          <IconButton label={t("close")} icon={X} onClick={onClose} />
        </div>
      </div>
      <div className="px-4 py-1.5 border-b border-border bg-muted/30">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="w-3.5 h-3.5 flex-shrink-0" />
          {t("consistency.aiDisclaimer")}
        </p>
      </div>
    </>
  );
}
