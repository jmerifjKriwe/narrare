import { useTranslation } from "@shell/lib/i18n";
import type { Job } from "@shell/lib/api/client";

/**
 * A durable job shown as its row's state (spec §9 D10): the UI never holds
 * a connection to the work, it polls the row — and this is what the poll
 * sees. Four visible states, each carrying its own assert-friendly
 * `data-job-status` attribute: queued and running promise movement (running
 * shows the handler's progress when it has reported one), failed names its
 * error, and done reports the result count. A status that never says which
 * of these it is would leave the writer waiting on nothing.
 */
export function JobStatus({ job }: { job: Job }) {
  const t = useTranslation();
  switch (job.status) {
    case "queued":
      return (
        <p role="status" data-job-status="queued" className="text-sm text-muted">
          {t("jobs.queued")}
        </p>
      );
    case "running":
      return (
        <p role="status" data-job-status="running" className="text-sm text-muted">
          {job.progress === null
            ? t("jobs.running")
            : t("jobs.runningProgress", { progress: job.progress / 100 })}
        </p>
      );
    case "failed":
      return (
        <p role="alert" data-job-status="failed" className="text-sm text-danger">
          {t("jobs.failed", { error: job.error ?? "" })}
        </p>
      );
    case "done":
      return (
        <p role="status" data-job-status="done" className="text-sm text-muted">
          {t("jobs.done", { count: suggestions(job) })}
        </p>
      );
    default:
      // A status outside the lane's state machine is contract drift, and
      // hiding it would look like silence. Shown raw, it is at least seen.
      return (
        <p role="status" data-job-status={job.status} className="text-sm text-muted">
          {job.status}
        </p>
      );
  }
}

/** The done result this product's jobs report: how many suggestions the
 *  extraction filed. A result without the key is a handler contract change,
 *  and zero is the honest count until the shape catches up. */
function suggestions(job: Job): number {
  const value = job.result?.["suggestions"];
  return typeof value === "number" ? value : 0;
}
