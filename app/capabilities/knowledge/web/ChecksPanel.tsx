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
import { Button } from "@shell/ui/Button";
import { JobStatus } from "@shell/ui/JobStatus";
import { Notice } from "@shell/ui/Notice";
import { Panel } from "@shell/ui/Panel";

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

  /** Enqueue a check and select its job for polling, or expose the enqueue failure. */
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
      <h3 id={headingId} className="text-body font-semibold">
        {t("knowledge.checksHeading")}
      </h3>
      <div className="mt-2">
        {/* Secondary: a second filled Button beside the extraction's
            trigger would leave the dock two primaries with no reading
            order (L1). The dialogs' trigger paint is P17's (R37) and stays
            out of this panel's count. */}
        <Button variant="secondary" onClick={() => void check()} disabled={busy}>
          {t("knowledge.checkNovel")}
        </Button>
      </div>
      {enqueueFailed ? (
        <Notice tone="danger" live="alert" className="mt-2">
          {t("knowledge.checkError")}
        </Notice>
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
        <Notice tone="danger" live="alert" className="mt-2">
          {t("knowledge.errorCheckJob")}
        </Notice>
      ) : null}
      {/* The findings queue outlives the job that filled it: a dock
          reopened later still owes the writer the decisions, so the cards
          render from the query, not from the job's lifecycle. A finding is
          the dock's own surface (P17's to restyle): the Panel holds the
          finding as its heading and the evidence beneath it, and the two
          decisions stand on shell Buttons — the pair is two equals, neither
          fills a primary (L1), and both stay always visible. */}
      {findings.isError ? (
        // The queue's own outage, named apart from the dock's other
        // failures: the findings, the suggestions and the entity list can
        // all go dark together, and a writer reading several alerts must
        // know which answer is missing. Silence would read as a spent
        // queue — the same mask the suggestions queue never wears.
        <Notice tone="danger" live="alert" className="mt-2">
          {t("knowledge.errorFindings")}
        </Notice>
      ) : (
        (findings.data ?? []).map((finding) => (
          // The labelled section is the card's name for assistive tech:
          // one "Consistency finding" region per contradiction, the way the
          // proposal cards it replaces named themselves.
          <section key={finding.id} aria-label={t("knowledge.findingTitle")} className="mt-4">
            <Panel>
              <h4 className="text-emph font-semibold">{finding.summary}</h4>
              <p className="mt-2 whitespace-pre-wrap text-body leading-relaxed text-muted">
                {finding.detail ?? ""}
              </p>
              <div className="mt-3 flex gap-2">
                <Button
                  onClick={() => {
                    void acknowledge
                      .mutateAsync(finding.id)
                      .then(() => announce(t("knowledge.findingAcknowledged")))
                      .catch(() => undefined);
                  }}
                >
                  {t("proposal.accept")}
                </Button>
                <Button
                  onClick={() => {
                    void dismiss
                      .mutateAsync(finding.id)
                      .then(() => announce(t("knowledge.findingDismissed")))
                      .catch(() => undefined);
                  }}
                >
                  {t("proposal.discard")}
                </Button>
              </div>
            </Panel>
          </section>
        ))
      )}
    </section>
  );
}
