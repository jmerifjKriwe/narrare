import { ArrowLeft, Info, RefreshCw, Shield, X } from "lucide-react";

type ViewState = "idle" | "loading" | "results" | "error";

interface ConsistencyPanelHeaderProps {
  viewState: ViewState;
  isPending: boolean;
  onClose: () => void;
  onRefresh: () => void;
  t: (key: string) => string;
}

export function ConsistencyPanelHeader({
  viewState,
  isPending,
  onClose,
  onRefresh,
  t,
}: ConsistencyPanelHeaderProps) {
  return (
    <>
      <div className="flex items-center justify-between p-4 border-b border-border bg-card">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
            aria-label={t("close")}
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <Shield className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0" />
            <h3 className="font-medium truncate">{t("consistency.title")}</h3>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
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
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
            aria-label={t("close")}
          >
            <X className="w-4 h-4" />
          </button>
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
