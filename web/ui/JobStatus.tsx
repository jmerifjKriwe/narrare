import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import type { Job } from "@shell/lib/api/client";

/**
 * Each job kind names its own outcome: the key of the done copy and the
 * result key its count lives under. The extraction reads its suggestions,
 * the consistency check its findings — a done row wearing another kind's
 * words would misreport the work, and a kind this map does not carry is
 * contract drift, shown raw below rather than silenced.
 */
const DONE_BY_KIND: Record<string, { doneKey: MessageKey; resultKey: string }> = {
  "extract-entities": { doneKey: "jobs.done.extract-entities", resultKey: "suggestions" },
  "check-consistency": { doneKey: "jobs.done.check-consistency", resultKey: "findings" },
};

/**
 * A durable job shown as its row's state (spec §9 D10): the UI never holds
 * a connection to the work, it polls the row — and this is what the poll
 * sees. Four visible states, each carrying its own assert-friendly
 * `data-job-status` attribute: queued and running promise movement (running
 * shows the handler's progress when it has reported one), failed names its
 * error, and done reports the result count its own kind reads. A status
 * that never says which of these it is would leave the writer waiting on
 * nothing.
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
    case "done": {
      const outcome = DONE_BY_KIND[job.kind];
      // A done row can still owe the writer a caveat: a read that stopped at
      // the bound is reported beside the count, or the count would pass for
      // the whole chapter.
      const truncated = job.result?.["truncated"] === true;
      return (
        <>
          <p role="status" data-job-status="done" className="text-sm text-muted">
            {outcome === undefined
              ? // A kind without an entry is contract drift, and hiding it
                // would look like silence. Shown raw, it is at least seen —
                // the same rule the unknown status keeps below.
                job.kind
              : t(outcome.doneKey, { count: resultCount(job, outcome.resultKey) })}
          </p>
          {truncated ? (
            <p
              role="status"
              data-job-truncated="true"
              className="mt-1 text-sm text-muted"
            >
              {t("jobs.truncated")}
            </p>
          ) : null}
        </>
      );
    }
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

/** The done result's count under the kind's own key. A result without the
 *  key is a handler contract change, and zero is the honest count until
 *  the shape catches up. */
function resultCount(job: Job, resultKey: string): number {
  const value = job.result?.[resultKey];
  return typeof value === "number" ? value : 0;
}
