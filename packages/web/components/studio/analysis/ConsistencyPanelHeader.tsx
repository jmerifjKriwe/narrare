import { Info, Loader2, RefreshCw, Shield } from "lucide-react";
import type { useTranslations } from "next-intl";
import { PanelHeader } from "@/components/ui/panel-header";

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
      <PanelHeader
        title={t("consistency.title")}
        icon={Shield}
        actions={
          <>
            {/* Stop button during loading */}
            {isLoading && onCancel && (
              <button
                type="button"
                onClick={onCancel}
                className="flex items-center gap-1.5 rounded-md border border-red-300 px-3 py-1.5 text-xs text-red-600 transition-colors hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950/30"
                aria-label={tStudio("aiActions.stop")}
              >
                <Loader2 className="h-3.5 w-3.5" />
                {tStudio("aiActions.stop")}
              </button>
            )}
            {viewState === "results" && (
              <button
                type="button"
                onClick={onRefresh}
                disabled={isPending}
                className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs transition-colors hover:bg-muted disabled:opacity-50"
                aria-label={t("refresh")}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isPending ? "animate-spin" : ""}`} />
                {t("refresh")}
              </button>
            )}
          </>
        }
        closeLabel={t("close")}
        onClose={onClose}
      />
      <div className="border-b border-border bg-muted/30 px-4 py-1.5">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="h-3.5 w-3.5 shrink-0" />
          {t("consistency.aiDisclaimer")}
        </p>
      </div>
    </>
  );
}
