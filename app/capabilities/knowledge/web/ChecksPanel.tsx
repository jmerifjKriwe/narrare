import { useParams } from "@tanstack/react-router";
import { useEffect, useId, useState } from "react";

import { announce } from "@shell/lib/announce";
import { useTranslation } from "@shell/lib/i18n";
import {
  queryClient,
  useAcknowledgeFinding,
  useDismissFinding,
  useEnqueueCheck,
  useFindingsQuery,
  useJobQuery,
} from "@shell/lib/query";
import { JobStatus } from "@shell/ui/JobStatus";
import { ProposalCard } from "@shell/ui/ProposalCard";

/** The whole-novel consistency check and its review: the check runs as a
 *  durable job on the same lane the chapter-scoped extraction rides — the
 *  panel polls the row, never a connection — and the findings it files
 *  arrive as proposal cards, one per contradiction, acknowledged or
 *  dismissed. */
export function ChecksPanel() {
  const t = useTranslation();
  const { id: novelId } = useParams({ from: "/novels/$id" });
  const [jobId, setJobId] = useState<string | null>(null);
  const [enqueueFailed, setEnqueueFailed] = useState(false);
  const job = useJobQuery(jobId);
  const enqueue = useEnqueueCheck(novelId);
  const findings = useFindingsQuery(novelId);
  const acknowledge = useAcknowledgeFinding(novelId);
  const dismiss = useDismissFinding(novelId);
  const headingId = useId();

  // The settled job decides the queue: the row turning done or failed is
  // the moment the findings exist (or provably will not), so that is when
  // the pending queue refetches — the poll publishes its own finding.
  const settled = job.data?.status === "done" || job.data?.status === "failed";
  useEffect(() => {
    if (!settled) return;
    void queryClient.invalidateQueries({ queryKey: ["knowledge", "findings", novelId] });
  }, [settled, novelId]);

  // The poll can fail like any fetch: the service going down under an
  // outstanding job leaves the row's answer missing. A missing answer is
  // an error, not a promise of movement — the queued/running row promised
  // progress, and an unanswered poll must not wear that promise.
  const pollFailed = jobId !== null && job.isError;

  // One check at a time: the trigger stays closed while its enqueue POST
  // is in flight or the job it filed is still outstanding, because a
  // second click would stack a duplicate job and a duplicate review queue
  // behind the first — the extraction's single-shot rule, unchanged. The
  // same three things hand the button back: a settled row, a poll that
  // met the dead service, a refused enqueue.
  const busy = enqueue.isPending || (jobId !== null && !settled && !pollFailed);

  async function check() {
    setEnqueueFailed(false);
    try {
      const accepted = await enqueue.mutateAsync();
      setJobId(accepted.job_id);
    } catch {
      // The enqueue itself failed — the job lane never heard of it, so the
      // queue is untouched and the retry is the same button again.
      setEnqueueFailed(true);
    }
  }

  return (
    <section aria-labelledby={headingId} className="mt-6">
      <h3 id={headingId} className="text-sm font-semibold">
        {t("knowledge.checksHeading")}
      </h3>
      <button
        type="button"
        onClick={() => void check()}
        disabled={busy}
        className="mt-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:opacity-50"
      >
        {t("knowledge.checkNovel")}
      </button>
      {enqueueFailed ? (
        <p role="alert" className="mt-2 text-sm text-danger">
          {t("knowledge.checkError")}
        </p>
      ) : null}
      {job.data && !(pollFailed && (job.data.status === "queued" || job.data.status === "running")) ? (
        // The last-known row renders only what it can still stand behind:
        // a done or failed row is a fact and stays beside the outage's
        // alert; a queued or running row is a promise of movement, and a
        // dead poll cannot keep that promise.
        <div className="mt-2">
          <JobStatus job={job.data} />
        </div>
      ) : null}
      {pollFailed ? (
        // The failed poll names itself where the trigger it unlocked sits:
        // the outage reads as an outage, and the retry is one click away.
        <p role="alert" className="mt-2 text-sm text-danger">
          {t("knowledge.errorCheckJob")}
        </p>
      ) : null}
      {/* The findings queue outlives the job that filled it: a dock
          reopened later still owes the writer the decisions, so the cards
          render from the query, not from the job's lifecycle. */}
      {findings.isError ? (
        // The queue's own outage, named apart from the dock's other
        // failures: the findings, the suggestions and the entity list can
        // all go dark together, and a writer reading several alerts must
        // know which answer is missing. Silence would read as a spent
        // queue — the same mask the suggestions queue never wears.
        <p role="alert" className="mt-2 text-sm text-danger">
          {t("knowledge.errorFindings")}
        </p>
      ) : (
        (findings.data ?? []).map((finding) => (
          <ProposalCard
            key={finding.id}
            titleKey="knowledge.findingTitle"
            body={finding.detail ?? ""}
            onAccept={() => {
              void acknowledge
                .mutateAsync(finding.id)
                .then(() => announce(t("knowledge.findingAcknowledged")))
                .catch(() => undefined);
            }}
            onDiscard={() => {
              void dismiss
                .mutateAsync(finding.id)
                .then(() => announce(t("knowledge.findingDismissed")))
                .catch(() => undefined);
            }}
          >
            <p className="mt-2 text-sm font-medium">{finding.summary}</p>
          </ProposalCard>
        ))
      )}
    </section>
  );
}
