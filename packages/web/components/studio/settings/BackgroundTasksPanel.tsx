"use client";

/**
 * BackgroundTasksPanel — read-only monitor for the TaskIQ background task queue.
 *
 * Shows the broker process status and the list of registered background tasks.
 * Polls ``GET /tasks/status`` every 10 seconds via TanStack Query. There is no
 * retry/manage UI here — that is future work (see INFRA-007).
 */

import { useQuery } from "@tanstack/react-query";
import { Activity, AlertCircle, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { TaskStatus } from "@/lib/api/client";
import { tasksApi } from "@/lib/api/client";
import { cn } from "@/lib/utils";

/** Polling interval for the task status query (10s). */
const REFRESH_INTERVAL_MS = 10_000;

/**
 * Known registered task names. Only these have friendly i18n labels; any future
 * backend task without a key falls back to its raw ``task_name`` string so the
 * panel never throws on an unknown translation key.
 */
const KNOWN_TASK_NAMES: ReadonlySet<string> = new Set([
  "embed_source",
  "process_feedback_memory",
  "run_preference_analysis",
  "wiki_generate_chapter",
  "wiki_generate_entity",
  "wiki_mark_all_stale",
  "wiki_refresh_summary",
]);

export function BackgroundTasksPanel() {
  const t = useTranslations("studio");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["tasks", "status"],
    queryFn: tasksApi.getStatus,
    refetchInterval: REFRESH_INTERVAL_MS,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12" role="status">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex items-center gap-3 py-8 text-destructive" role="alert">
        <AlertCircle className="w-5 h-5 shrink-0" />
        <span className="text-sm">{t("backgroundTasks.loadFailed")}</span>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-medium mb-1">{t("backgroundTasks.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("backgroundTasks.description")}</p>
      </div>

      <div className="space-y-4">
        <BrokerStatusCard started={data.broker_started} />

        <RegisteredTasksCard status={data} />
      </div>

      <p className="mt-4 text-xs text-muted-foreground">{t("backgroundTasks.refreshInterval")}</p>
    </div>
  );
}

// --- Sub-components ---------------------------------------------------------

function BrokerStatusCard({ started }: { readonly started: boolean }) {
  const t = useTranslations("studio");

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center shrink-0">
            <Activity className="w-6 h-6" />
          </div>
          <div>
            <h3 className="font-medium">{t("backgroundTasks.brokerStatus.title")}</h3>
            <p className="text-sm text-muted-foreground">
              {t("backgroundTasks.brokerStatus.description")}
            </p>
          </div>
        </div>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border whitespace-nowrap",
            started
              ? "bg-green-500/15 text-green-700 dark:text-green-400 border-green-500/30"
              : "bg-muted text-muted-foreground border-border",
          )}
          role="status"
          aria-live="polite"
        >
          <span
            className={cn(
              "w-1.5 h-1.5 rounded-full",
              started ? "bg-green-600 dark:bg-green-400" : "bg-muted-foreground",
            )}
            aria-hidden="true"
          />
          {started
            ? t("backgroundTasks.brokerStatus.started")
            : t("backgroundTasks.brokerStatus.stopped")}
        </span>
      </div>
    </div>
  );
}

function RegisteredTasksCard({ status }: { readonly status: TaskStatus }) {
  const t = useTranslations("studio");

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-medium">{t("backgroundTasks.registeredTasks")}</h3>
        <span className="text-sm text-muted-foreground">
          {t("backgroundTasks.taskCount", { count: status.registered_task_count })}
        </span>
      </div>

      {status.registered_tasks.length === 0 ? (
        <p className="text-sm text-muted-foreground" role="status">
          {t("backgroundTasks.noTasks")}
        </p>
      ) : (
        <ul className="space-y-1.5">
          {status.registered_tasks.map((name) => {
            const label = KNOWN_TASK_NAMES.has(name) ? t(`backgroundTasks.taskName.${name}`) : name;
            return (
              <li
                key={name}
                className="flex items-center gap-2 px-3 py-2 rounded-md bg-background/50 border border-border"
              >
                <span className="w-2 h-2 rounded-full bg-primary shrink-0" aria-hidden="true" />
                <span className="text-sm">{label}</span>
                <code className="ml-auto text-xs text-muted-foreground">{name}</code>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
