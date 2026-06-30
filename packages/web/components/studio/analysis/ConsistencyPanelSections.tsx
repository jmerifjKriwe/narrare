import { AlertTriangle, Loader2, RefreshCw, Wifi, WifiOff } from "lucide-react";
import type { useTranslations } from "next-intl";
import type { ConsistencyResponse } from "@/lib/api/analysis";
import type { ConsistencyStagePayload } from "@/lib/hooks/useConsistencyStream";
import { ConsistencyIssueList } from "./ConsistencyIssueList";

type Scope = "current" | "selected" | "all";
type StudioTranslator = ReturnType<typeof useTranslations>;

interface ScopeSelectorProps {
  scope: Scope;
  onScopeChange: (scope: Scope) => void;
  t: (key: string) => string;
}

interface ResultsProps {
  result: ConsistencyResponse;
  t: (key: string, params?: Record<string, unknown>) => string;
}

export function ConsistencyScopeSelector({ scope, onScopeChange, t }: ScopeSelectorProps) {
  return (
    <div className="px-4 py-2.5 border-b border-border bg-muted/20">
      <p className="text-xs font-medium text-muted-foreground mb-1.5">
        {t("consistency.scope.label")}
      </p>
      <div className="flex gap-1">
        {(["current", "selected", "all"] as const).map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => onScopeChange(option)}
            className={`flex-1 px-2 py-1 text-xs rounded transition-colors ${
              scope === option
                ? "bg-primary text-primary-foreground font-medium"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
            aria-pressed={scope === option}
          >
            {t(`consistency.scope.${option}`)}
          </button>
        ))}
      </div>
    </div>
  );
}

export function ConsistencyLoadingState({
  elapsed,
  loadingStep,
  progress,
  t,
}: {
  elapsed: number;
  loadingStep: string;
  /** Stage snapshot from the SSE stream, null when not yet available. */
  progress: ConsistencyStagePayload | null;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="relative mb-6">
        <div className="w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-green-600 animate-spin" />
        </div>
      </div>
      <p className="text-lg font-medium mb-2">
        {t("consistency.loadingElapsed", { seconds: elapsed })}
      </p>
      {progress?.message ? (
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">{progress.message}</p>
          {progress.progress > 0 && (
            <p className="text-xs text-muted-foreground">{Math.round(progress.progress * 100)}%</p>
          )}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{t(`consistency.progress.${loadingStep}`)}</p>
      )}
    </div>
  );
}

export function ConsistencyErrorState({
  errorMessage,
  isConnectionLost,
  onRetry,
  t,
  tStudio,
}: {
  errorMessage: string;
  isConnectionLost: boolean;
  onRetry: () => void;
  t: (key: string) => string;
  tStudio: StudioTranslator;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
        {isConnectionLost ? (
          <WifiOff className="w-6 h-6 text-red-500" />
        ) : (
          <AlertTriangle className="w-6 h-6 text-red-500" />
        )}
      </div>
      <p className="text-lg font-medium mb-1">
        {isConnectionLost ? tStudio("aiActions.connectionLost") : t("error")}
      </p>
      <p className="text-sm text-muted-foreground mb-4">{errorMessage}</p>
      <button
        type="button"
        onClick={onRetry}
        className="flex items-center gap-1.5 px-4 py-2 text-sm border border-border rounded-md hover:bg-muted transition-colors"
      >
        {isConnectionLost ? (
          <>
            <Wifi className="w-4 h-4" />
            {tStudio("aiActions.connectionLostRetry")}
          </>
        ) : (
          <>
            <RefreshCw className="w-4 h-4" />
            {tStudio("aiActions.retry")}
          </>
        )}
      </button>
    </div>
  );
}

export function ConsistencyResults({ result, t }: ResultsProps) {
  return (
    <>
      <section className="flex items-center justify-center gap-3">
        <SeverityBadge
          count={result.error_count}
          label={t("consistency.severity.error")}
          colorClass="bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400"
        />
        <SeverityBadge
          count={result.warning_count}
          label={t("consistency.severity.warning")}
          colorClass="bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400"
        />
        <SeverityBadge
          count={result.info_count}
          label={t("consistency.severity.info")}
          colorClass="bg-blue-50 dark:bg-blue-950/20 text-blue-700 dark:text-blue-400"
        />
      </section>
      <section>
        <h4 className="text-sm font-medium mb-2">{t("consistency.overallAssessment")}</h4>
        <p className="text-sm text-muted-foreground">{result.overall_assessment}</p>
      </section>
      <section>
        <h4 className="text-sm font-medium mb-3">
          {t("consistency.issues", { count: result.total_issues })}
        </h4>
        <ConsistencyIssueList issues={result.issues} t={t} />
      </section>
    </>
  );
}

function SeverityBadge({
  count,
  label,
  colorClass,
}: {
  count: number;
  label: string;
  colorClass: string;
}) {
  return (
    <div
      className={`flex flex-col items-center gap-1 px-4 py-2 rounded-lg border border-border ${colorClass}`}
    >
      <span className="text-xl font-bold">{count}</span>
      <span className="text-xs font-medium">{label}</span>
    </div>
  );
}
